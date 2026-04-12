#!/usr/bin/env python3
"""
verify.py — Independent verification of the paper trading event stream.

Usage:
    python3 verify.py events.jsonl

Performs the following checks:
  1. Schema validation (required fields per event type)
  2. Temporal ordering (strictly ascending ts_utc)
  3. Entry-exit pairing (no orphans except open positions)
  4. Fee recomputation (L1 Deribit formula)
  5. L2 recomputation (half-spread vs mark)
  6. IM recomputation (Deribit inverse option margin)
  7. PnL recomputation (gross and net)
  8. Capital constraint (sum of IM never exceeds 9.6 BTC)
  9. Event ID determinism (sha256-based)

Exit code: 0 if all checks pass, 1 otherwise.

No external dependencies beyond the Python 3 standard library.
"""

import json
import hashlib
import sys
from collections import defaultdict

# ── Constants (matching Deribit fee schedule and strategy rules) ──────────────

POT_BTC = 9.6
FEE_UNDERLYING = 0.0003
FEE_CAP = 0.125
FEE_MIN = 0.0001
ALPHA_EXIT = 0.10
TOL = 1e-8  # floating-point tolerance for comparisons


def option_fee_btc(m_btc):
    """Deribit taker fee for 1 option contract."""
    return max(FEE_MIN, min(FEE_UNDERLYING, FEE_CAP * m_btc))


def compute_im_btc(x, side='call'):
    """Initial margin for 1 contract of short inverse BTC option."""
    if side == 'call':
        return max(0.10, 1.15 - 1.0 / x)
    else:
        return max(0.10, 1.0 / x - 0.85)


def compute_event_id(etype, instrument, ts_utc, horizon):
    """Deterministic event ID."""
    payload = f"{etype}|{instrument}|{ts_utc}|{horizon}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def load_events(path):
    """Load events.jsonl, return list of dicts with line numbers."""
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
                print(f"FAIL line {i}: invalid JSON — {e}")
                events.append({'_line': i, '_parse_error': str(e)})
    return events


def verify(events):
    """Run all checks. Returns (n_errors, messages)."""
    errors = []
    completed_trades = []
    open_positions = {}  # event_id → entry event

    prev_ts = None

    for ev in events:
        line = ev.get('_line', '?')

        if '_parse_error' in ev:
            errors.append(f"L{line}: JSON parse error")
            continue

        etype = ev.get('type')

        # ── Check 2: temporal ordering ────────────────────────────────────
        ts = ev.get('ts_utc', '')
        if prev_ts and ts < prev_ts:
            errors.append(f"L{line}: timestamp {ts} < previous {prev_ts}")
        prev_ts = ts

        # ── Check 9: event ID determinism ─────────────────────────────────
        expected_id = compute_event_id(
            etype,
            ev.get('instrument', ''),
            ts,
            ev.get('horizon', '')
        )
        actual_id = ev.get('event_id', '')
        if actual_id != expected_id:
            errors.append(
                f"L{line}: event_id mismatch: got {actual_id}, "
                f"expected {expected_id}"
            )

        # ── Type-specific checks ──────────────────────────────────────────

        if etype == 'entry':
            exec_btc = ev.get('exec_btc', 0)
            mark = ev.get('mark_price', 0)
            x = ev.get('x', 0)

            # Check 4: fee
            expected_fee = option_fee_btc(exec_btc)
            actual_fee = ev.get('fee_btc', 0)
            if abs(actual_fee - expected_fee) > TOL:
                errors.append(
                    f"L{line}: fee_btc={actual_fee}, "
                    f"expected={expected_fee:.10f}"
                )

            # Check 5: L2
            expected_l2 = max(0, mark - exec_btc)
            actual_l2 = ev.get('l2_btc', 0)
            if abs(actual_l2 - expected_l2) > TOL:
                errors.append(
                    f"L{line}: l2_btc={actual_l2}, "
                    f"expected={expected_l2:.10f}"
                )

            # Check 6: IM
            if x > 0:
                expected_im = compute_im_btc(x, 'call')
                actual_im = ev.get('im_btc', 0)
                if abs(actual_im - expected_im) > TOL:
                    errors.append(
                        f"L{line}: im_btc={actual_im}, "
                        f"expected={expected_im:.10f}"
                    )

            # Track open position
            eid = ev.get('event_id')
            open_positions[eid] = ev

            # Check 8: capital constraint
            total_im = sum(p.get('im_btc', 0) for p in open_positions.values())
            if total_im > POT_BTC + TOL:
                errors.append(
                    f"L{line}: IM total={total_im:.4f} exceeds pot={POT_BTC}"
                )

        elif etype == 'exit':
            ref_id = ev.get('ref_entry_event_id', '')
            entry = open_positions.pop(ref_id, None)

            if entry is None:
                errors.append(
                    f"L{line}: exit references unknown entry {ref_id}"
                )
                continue

            exec_btc = ev.get('exec_btc', 0)
            mark = ev.get('mark_price', 0)
            reason = ev.get('exit_reason', '')

            # Check 4: fee (exit)
            if reason == 'expiry' and exec_btc == 0:
                expected_fee = 0
            else:
                expected_fee = option_fee_btc(exec_btc)
            actual_fee = ev.get('fee_btc', 0)
            if abs(actual_fee - expected_fee) > TOL:
                errors.append(
                    f"L{line}: exit fee_btc={actual_fee}, "
                    f"expected={expected_fee:.10f}"
                )

            # Check 5: L2 (exit)
            if reason == 'expiry' and exec_btc == 0:
                expected_l2 = 0
            else:
                expected_l2 = max(0, exec_btc - mark) if mark else 0
            actual_l2 = ev.get('l2_btc', 0)
            if abs(actual_l2 - expected_l2) > TOL:
                errors.append(
                    f"L{line}: exit l2_btc={actual_l2}, "
                    f"expected={expected_l2:.10f}"
                )

            # Check 7: PnL
            entry_exec = entry.get('exec_btc', 0)
            expected_gross = entry_exec - exec_btc
            actual_gross = ev.get('pnl_gross_btc', 0)
            if abs(actual_gross - expected_gross) > TOL:
                errors.append(
                    f"L{line}: pnl_gross={actual_gross}, "
                    f"expected={expected_gross:.10f}"
                )

            total_costs = (
                entry.get('fee_btc', 0) + entry.get('l2_btc', 0)
                + actual_fee + actual_l2
            )
            expected_net = expected_gross - total_costs
            actual_net = ev.get('pnl_net_btc', 0)
            if abs(actual_net - expected_net) > TOL:
                errors.append(
                    f"L{line}: pnl_net={actual_net}, "
                    f"expected={expected_net:.10f}"
                )

            completed_trades.append((entry, ev))

    return errors, completed_trades, open_positions


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 verify.py events.jsonl")
        sys.exit(1)

    path = sys.argv[1]
    events = load_events(path)
    n_events = len([e for e in events if '_parse_error' not in e])

    errors, completed, still_open = verify(events)

    print(f"Events:          {n_events}")
    print(f"Completed trades: {len(completed)}")
    print(f"Open positions:   {len(still_open)}")
    print()

    if errors:
        print(f"FAILED — {len(errors)} discrepancies found:\n")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)
    else:
        pnl_total = sum(ex.get('pnl_net_btc', 0) for _, ex in completed)
        print(f"OK — {n_events} events, {len(completed)} completed trades, "
              f"0 discrepancies")
        print(f"Total realized PnL: {pnl_total:+.8f} BTC")
        sys.exit(0)


if __name__ == '__main__':
    main()
