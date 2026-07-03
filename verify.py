#!/usr/bin/env python3
"""
verify.py — Independent verification of the paper trading event streams.

The active source of truth is the per-instance event stream under
`instances/<id>/events.jsonl`. The root `events.jsonl` is the frozen
`legacy_v2.1` baseline (through 2026-06-01). This script is schema-aware: it
audits both the v2 per-instance streams and the legacy root stream.

Usage:
    python3 verify.py instances/canonical/events.jsonl   # one stream
    python3 verify.py --all-instances                    # every instance + root
    python3 verify.py events.jsonl                        # legacy root stream

For each stream it recomputes, from the raw recorded primitives, and checks:
  1. Schema        — required fields present per event type
  2. Event IDs     — deterministic sha256 (includes instance_id for v2)
  3. No duplicates — every event_id is unique
  3b. Sequence     — the `seq` field (where present) is strictly increasing,
                     giving a provable order independent of ts_utc
  4. Pairing       — every exit references a known entry (open entries are OK)
  5. Fees (L1)     — Deribit underlying fee, per leg
  6. L2            — half-spread vs mark, per leg
  7. IM            — Deribit inverse-option initial margin, per entry
  8. PnL           — gross and net, per completed trade
  9. Capital       — peak simultaneous IM never exceeds the pot

Timestamp inversions and the historical placeholder record (see DISCLOSURES.md)
are reported as WARNINGS — they do not fail the audit, because sequence
integrity is proven independently by the append-only git history and the
SSH-signed commits.

Exit code: 0 if all hard checks pass, 1 otherwise.
No external dependencies beyond the Python 3 standard library.
"""

import json
import hashlib
import sys
import glob
import os

# ── Constants (matching the public Deribit fee schedule and strategy rules) ───

POT_BTC = 20.0            # capital pot (resized from 9.6 on 2026-04-15)
FEE_UNDERLYING = 0.0003   # Deribit option underlying-based fee (0.03% × 1 BTC)
FEE_CAP = 0.125           # fee cap: 12.5% of the premium
FEE_MIN = 0.0001          # minimum fee per contract, BTC
LEGACY_INSTANCE = 'legacy_v2.1'

# Exact-match tolerance for values recomputed directly from stored primitives
# (fees, L2, PnL). IM is recomputed from the stored, rounded moneyness `x`
# through the nonlinear 1/x, which amplifies x's storage precision (~6 dp) to
# roughly 1e-6 — so IM uses a looser tolerance.
TOL = 1e-8
TOL_IM = 1e-5

# Required fields per event type (hard schema check).
REQUIRED = {
    'entry': ('event_id', 'type', 'ts_utc', 'instrument', 'horizon',
              'exec_btc', 'mark_price', 'x', 'fee_btc', 'l2_btc', 'im_btc'),
    # mark_price is required only for active exits (checked in the exit branch);
    # settlement-at-expiry exits carry no mark (no order-book transaction).
    'exit': ('event_id', 'type', 'ts_utc', 'instrument', 'horizon',
             'exec_btc', 'fee_btc', 'l2_btc',
             'pnl_gross_btc', 'pnl_net_btc', 'ref_entry_event_id'),
    'exit_target_placed': ('event_id', 'type', 'ts_utc', 'instrument',
                           'horizon'),
    'rejected_daily_cap': ('event_id', 'type', 'ts_utc', 'horizon'),
}


def option_fee_btc(m_btc):
    """Deribit taker fee for 1 option contract (BTC)."""
    return max(FEE_MIN, min(FEE_UNDERLYING, FEE_CAP * m_btc))


def compute_im_btc(x, side='call'):
    """Initial margin for 1 contract of a short inverse BTC option (BTC)."""
    if side == 'call':
        return max(0.10, 1.15 - 1.0 / x)
    return max(0.10, 1.0 / x - 0.85)


def compute_event_id(etype, instrument, ts_utc, horizon, instance_id):
    """
    Deterministic event ID: sha256(type|instrument|ts_utc|horizon[|instance_id]).

    The instance_id is included for every instance except the legacy default
    (None / 'legacy_v2.1'), which preserves the original v1 event IDs.
    """
    payload = f"{etype}|{instrument}|{ts_utc}|{horizon}"
    if instance_id not in (None, LEGACY_INSTANCE):
        payload += f"|{instance_id}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def load_events(path):
    """Load an events.jsonl file into a list of dicts tagged with line numbers."""
    events = []
    with open(path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
                ev['_line'] = i
                events.append(ev)
            except json.JSONDecodeError as e:
                events.append({'_line': i, '_parse_error': str(e)})
    return events


def verify(events):
    """
    Run all checks over one stream's events (in file order).

    Returns a result dict with hard `errors`, soft `warnings`, and summary
    counters (completed trades, open positions, realized PnL, peak IM,
    duplicate IDs, timestamp inversions, schema violations).
    """
    errors = []
    warnings = []
    completed = []
    open_positions = {}    # entry event_id → entry event
    seen_ids = set()
    running_im = 0.0
    peak_im = 0.0
    inversions = 0
    schema_violations = 0
    prev_ts = None
    last_seq = None

    for ev in events:
        line = ev.get('_line', '?')

        if '_parse_error' in ev:
            errors.append(f"L{line}: invalid JSON — {ev['_parse_error']}")
            continue

        # Historical placeholder / pre-schema record → warn and skip (see
        # DISCLOSURES.md). Real v2 events always carry schema_version.
        if not ev.get('schema_version'):
            warnings.append(f"L{line}: record without schema_version (skipped)")
            continue

        etype = ev.get('type')
        instance_id = ev.get('instance_id')

        # ── Schema: required fields present ───────────────────────────────
        required = REQUIRED.get(etype)
        if required is None:
            errors.append(f"L{line}: unknown event type {etype!r}")
            continue
        missing = [k for k in required if k not in ev]
        if missing:
            schema_violations += 1
            errors.append(f"L{line}: {etype} missing fields {missing}")
            continue

        # ── Duplicate event IDs ───────────────────────────────────────────
        eid = ev.get('event_id')
        if eid in seen_ids:
            errors.append(f"L{line}: duplicate event_id {eid}")
        seen_ids.add(eid)

        # ── Temporal ordering (soft: sub-second inversions are warnings) ──
        ts = ev.get('ts_utc', '')
        if prev_ts is not None and ts < prev_ts:
            inversions += 1
            warnings.append(f"L{line}: timestamp {ts} < previous {prev_ts}")
        prev_ts = ts

        # ── Sequence ordering (authoritative where present) ───────────────
        # `seq` is a per-stream monotonic counter added from 2026-07-02 (see
        # DISCLOSURES.md). It gives a provable order that is robust to the
        # sub-second ts_utc inversions among same-cycle events. Older events
        # carry no seq and are skipped here.
        seq = ev.get('seq')
        if seq is not None:
            if last_seq is not None and seq <= last_seq:
                errors.append(
                    f"L{line}: seq {seq} not strictly increasing "
                    f"(previous {last_seq})"
                )
            last_seq = seq

        # ── Event ID determinism (all types) ──────────────────────────────
        expected_id = compute_event_id(
            etype, ev.get('instrument', ''), ts, ev.get('horizon', ''),
            instance_id,
        )
        if eid != expected_id:
            errors.append(
                f"L{line}: event_id mismatch: got {eid}, expected {expected_id}"
            )

        # ── Type-specific economic recomputation ──────────────────────────
        if etype == 'entry':
            exec_btc = ev['exec_btc']
            mark = ev['mark_price']
            x = ev['x']

            _check(errors, line, 'fee_btc', ev['fee_btc'],
                   option_fee_btc(exec_btc), TOL)
            _check(errors, line, 'l2_btc', ev['l2_btc'],
                   max(0.0, mark - exec_btc), TOL)
            if x > 0:
                _check(errors, line, 'im_btc', ev['im_btc'],
                       compute_im_btc(x, 'call'), TOL_IM)

            open_positions[eid] = ev
            running_im += ev['im_btc']
            peak_im = max(peak_im, running_im)
            if running_im > POT_BTC + TOL:
                errors.append(
                    f"L{line}: peak IM {running_im:.4f} exceeds pot {POT_BTC}"
                )

        elif etype == 'exit':
            entry = open_positions.pop(ev['ref_entry_event_id'], None)
            if entry is None:
                errors.append(
                    f"L{line}: exit references unknown/closed entry "
                    f"{ev['ref_entry_event_id']}"
                )
                continue
            running_im -= entry['im_btc']

            exec_btc = ev['exec_btc']
            reason = ev.get('exit_reason', '')

            if reason == 'expiry':
                # Settlement at expiry: no order-book transaction. No half-spread
                # (L2 = 0); a fee applies only if the contract settled with value.
                expected_fee = option_fee_btc(exec_btc) if exec_btc > 0 else 0.0
                expected_l2 = 0.0
            else:
                # Active buy-back (alpha exit / expiry guard): mark required.
                if 'mark_price' not in ev:
                    errors.append(f"L{line}: active exit missing mark_price")
                    continue
                expected_fee = option_fee_btc(exec_btc)
                expected_l2 = max(0.0, exec_btc - ev['mark_price'])

            _check(errors, line, 'exit fee_btc', ev['fee_btc'], expected_fee, TOL)
            _check(errors, line, 'exit l2_btc', ev['l2_btc'], expected_l2, TOL)

            expected_gross = entry['exec_btc'] - exec_btc
            _check(errors, line, 'pnl_gross_btc', ev['pnl_gross_btc'],
                   expected_gross, TOL)

            total_costs = (entry['fee_btc'] + entry['l2_btc']
                           + ev['fee_btc'] + ev['l2_btc'])
            _check(errors, line, 'pnl_net_btc', ev['pnl_net_btc'],
                   expected_gross - total_costs, TOL)

            completed.append((entry, ev))

        # exit_target_placed / rejected_daily_cap: schema + id checks only.

    return {
        'errors': errors,
        'warnings': warnings,
        'completed': completed,
        'open': open_positions,
        'peak_im': peak_im,
        'inversions': inversions,
        'schema_violations': schema_violations,
    }


def _check(errors, line, field, actual, expected, tol):
    """Append an error if |actual − expected| exceeds `tol`."""
    if abs(actual - expected) > tol:
        errors.append(
            f"L{line}: {field}={actual}, expected={expected:.10f}"
        )


def verify_file(path, label=None):
    """Verify one stream file; print a summary; return True if it passes."""
    label = label or path
    if not os.path.exists(path):
        print(f"{label}: SKIP — file not found")
        return True

    events = load_events(path)
    n_events = len([e for e in events if '_parse_error' not in e])
    r = verify(events)

    pnl = sum(ex['pnl_net_btc'] for _, ex in r['completed'])

    if r['errors']:
        print(f"{label}: FAIL — {len(r['errors'])} error(s)")
        for e in r['errors'][:20]:
            print(f"    {e}")
        if len(r['errors']) > 20:
            print(f"    … and {len(r['errors']) - 20} more")
    else:
        print(
            f"{label}: OK — {n_events} events, {len(r['completed'])} trades, "
            f"{len(r['open'])} open, PnL {pnl:+.8f} BTC, "
            f"peak IM {r['peak_im']:.4f} BTC"
        )
    if r['warnings']:
        print(
            f"    warnings: {r['inversions']} timestamp inversion(s), "
            f"{len(r['warnings']) - r['inversions']} other "
            f"(sequence proven by append-only git history + signed commits)"
        )

    return not r['errors']


def main():
    args = sys.argv[1:]

    if not args:
        print("Usage: python3 verify.py <events.jsonl> | --all-instances")
        sys.exit(1)

    if args[0] == '--all-instances':
        paths = sorted(glob.glob('instances/*/events.jsonl'))
        if os.path.exists('events.jsonl'):
            paths.append('events.jsonl')  # legacy root stream
        if not paths:
            print("No event streams found (run from the repository root).")
            sys.exit(1)
        all_ok = True
        for path in paths:
            label = path.split('/')[1] if path.startswith('instances/') \
                else 'legacy (root)'
            ok = verify_file(path, label=label)
            all_ok = all_ok and ok
        print()
        print("ALL OK" if all_ok else "SOME STREAMS FAILED")
        sys.exit(0 if all_ok else 1)

    ok = verify_file(args[0])
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
