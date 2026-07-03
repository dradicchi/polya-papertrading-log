# How to verify this track record

This document explains how a third party can independently verify the integrity and correctness of the paper trading log.

## Prerequisites

- Git 2.34+ (for SSH signature verification)
- Python 3.10+ (for PnL recomputation)
- OpenTimestamps client (optional, for blockchain timestamp verification): `pip install opentimestamps-client`

---

## Step 1 — Clone and verify commit signatures

```bash
git clone https://github.com/dradicchi/polya-papertrading-log.git
cd polya-papertrading-log

# Fetch the signer's public key from GitHub
curl -s https://github.com/dradicchi.keys > /tmp/dradicchi_keys.pub

# Create an allowed_signers file for local verification
echo "1715905+dradicchi@users.noreply.github.com $(cat /tmp/dradicchi_keys.pub | head -1)" > /tmp/allowed_signers

# Configure git to use it (temporary, repo-local)
git config gpg.ssh.allowedSignersFile /tmp/allowed_signers

# Verify all commits
git log --show-signature --oneline
```

Every commit should show `Good "git" signature for 1715905+dradicchi@users.noreply.github.com with ED25519 key SHA256:Xp/CnXQhSmdpBRLWhoOXENkBc3FRkMIJeOBFh+XJKUM`.

If any commit shows `No signature` or `BAD signature`, that commit was either made before the signing setup (only possible for the initial repo creation commit, if applicable) or has been tampered with.

On GitHub's web interface, each commit also displays a **Verified** badge. This is GitHub's own independent verification using the signing key registered on the author's profile.

---

## Step 2 — Verify the event stream integrity

The append-only property of `events.jsonl` can be checked by inspecting the git diff of each commit:

```bash
# Show which lines were added (never modified) in events.jsonl across all history
git log --follow -p -- events.jsonl | grep "^+{" | wc -l
# Should equal the number of lines in events.jsonl
wc -l < events.jsonl
```

If the two numbers match, every line was added exactly once and never edited. Any editing would appear as both a `+` (addition) and a `-` (removal) in the diff for the same line.

---

## Step 3 — Recompute P&L from raw events

`verify.py` is schema-aware. Audit one stream, or all of them at once:

```bash
python3 verify.py instances/canonical/events.jsonl   # the canonical benchmark
python3 verify.py --all-instances                    # every instance + legacy root
python3 verify.py events.jsonl                        # legacy root stream
```

For each stream, from the raw recorded primitives, it re-derives and checks:

1. **Schema validation:** every line parses as valid JSON with the required fields for its event type (`entry`, `exit`, `exit_target_placed`, `rejected_daily_cap`).
2. **Event ID determinism:** `event_id == sha256(type + "|" + instrument + "|" + ts_utc + "|" + horizon [+ "|" + instance_id])[:16]`. The `instance_id` is appended for every instance except the legacy default (`legacy_v2.1`), which keeps the original v1 IDs.
3. **No duplicate event IDs.**
3b. **Sequence ordering:** the `seq` field (a per-stream strictly-increasing integer, added 2026-07-02 — see `DISCLOSURES.md`) is checked to be strictly increasing where present. It gives an order provable from the file alone, robust to the sub-second `ts_utc` inversions among same-cycle events. Older events carry no `seq` and rely on the append-only git history.
4. **Entry-exit pairing:** every `exit` references a known `entry` via `ref_entry_event_id`; unmatched entries are currently-open positions (reported, not an error).
5. **Fee recomputation:** `fee_btc == max(0.0001, min(0.0003, 0.125 * exec_btc))` per leg (settlement-at-expiry exits carry a fee only if they settled with value).
6. **L2 recomputation:** entries `max(0, mark_price - exec_btc)`; active exits `max(0, exec_btc - mark_price)`; settlement-at-expiry exits `0` (no order-book transaction).
7. **IM recomputation:** `im_btc == max(0.10, 1.15 - 1/x)` for short CALL. Tolerance 1e-5 BTC (IM is derived from the stored, rounded `x` through `1/x`, which amplifies its ~6-dp storage precision).
8. **PnL recomputation:** `pnl_gross = entry.exec_btc - exit.exec_btc`; `pnl_net = pnl_gross - (entry.fee + entry.l2 + exit.fee + exit.l2)`, against the declared values. Tolerance 1e-8 BTC.
9. **Capital constraint:** peak simultaneous `im_btc` never exceeds the 20 BTC pot (resized from 9.6 on 2026-04-15 — see `DISCLOSURES.md`).

Output per stream: `OK — N events, M trades, K open, PnL ±X BTC, peak IM Y BTC` (or a list of failed checks with line numbers), plus `ALL OK` / `SOME STREAMS FAILED` for `--all-instances`.

**Warnings, not failures.** Two conditions are reported as warnings and do **not** fail the audit: (a) sub-second `ts_utc` inversions among events emitted within the same cycle, and (b) the single pre-schema placeholder record at the head of `instances/canonical/events.jsonl` (see `DISCLOSURES.md`). Sequence integrity is proven independently by the append-only git history (Step 2) and the SSH-signed commits (Step 1); these warnings do not affect any recomputed figure.

---

## Step 4 — Verify blockchain timestamp (optional)

Each event stream is timestamped into its own `timestamps/` directory: the
active per-instance streams under `instances/<id>/timestamps/`, and the frozen
legacy root stream under the root `timestamps/`. Each `.sha256` file records the
hash of the stream at a point in time, and its sibling `.sha256.ots` is the
OpenTimestamps proof. The `.sha256` file's internal label names which stream it
anchors (e.g. `instances/canonical/events.jsonl`).

If the `opentimestamps-client` is installed, verify the most recent proof for
the stream you are auditing — for the canonical benchmark:

```bash
# most recent proof for the canonical instance stream
latest=$(ls -1 instances/canonical/timestamps/*.sha256.ots | sort | tail -1)
ots verify "$latest"
# confirm it anchors the current stream hash
shasum -a 256 instances/canonical/events.jsonl
cat "${latest%.ots}"   # the recorded hash + stream label
```

Expected output: `Success! Bitcoin block NNNNNN attests existence as of YYYY-MM-DD`.

This proves that the instance's `events.jsonl` (with its specific SHA-256 hash) existed at or before the timestamp anchored in the Bitcoin blockchain. Combined with the append-only property from Step 2, this means no events could have been inserted retroactively before that anchor point.

Note: OTS proofs are generated per trading cycle for each instance that had activity. A fresh `.ots` starts as a *pending* proof and is upgraded to a Bitcoin-anchored proof within a few hours (run `ots upgrade <file>.ots`). Events recorded after the most recent anchor are covered by the SSH signatures (Step 1) but not yet by a blockchain timestamp; the next anchor covers them. Bitcoin-anchored coverage of the per-instance live streams begins 2026-07-02 (see [`DISCLOSURES.md`](DISCLOSURES.md)); earlier live-stream events are covered by the append-only git history and SSH signatures.

---

## Step 5 — Cross-check prices against public market data (optional, requires external data)

The events record the `best_bid`, `best_ask`, `mark_price`, and `s_underlying_usd` observed at the `ts_utc` of each event. An auditor with access to historical tick data from Deribit (e.g., via [tardis.dev](https://tardis.dev) or a personal recording) can verify:

1. That the declared instrument existed and was active at the declared timestamp.
2. That the declared `best_bid`/`best_ask`/`mark_price` are consistent with the historical order book at that moment (within a reasonable tolerance for latency — the public API has ~100ms propagation delay).
3. That the `s_underlying_usd` (BTC index) is consistent with the Deribit BTC index at that moment.

This step is the strongest form of verification — it proves not only that the math is correct, but that the market state described in the events actually occurred. However, it requires external data that this repository does not provide (to avoid copyright issues with tick data providers).

---

## Summary of trust layers

| Layer | What it proves | Strength |
|---|---|---|
| SSH-signed commits | Events were authored by the holder of the signing key | Strong (Ed25519 cryptographic) |
| GitHub Verified badge | GitHub independently confirms the signature | Strong (independent verifier) |
| Append-only JSONL + git diff | No past events were edited | Strong (Merkle chain) |
| OpenTimestamps | Events existed at or before the anchored timestamp | Very strong (Bitcoin blockchain) |
| PnL recomputation (`verify.py`) | Declared performance matches raw event data | Deterministic (mathematical) |
| External price cross-check | Declared market state actually occurred | Strongest (independent data source) |

No single layer is sufficient on its own. Together, they form a defense-in-depth that would require compromise of multiple independent systems (GitHub, Bitcoin blockchain, Deribit, the auditor's own clone) to defeat.
