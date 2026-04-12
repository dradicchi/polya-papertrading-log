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

```bash
python3 verify.py events.jsonl
```

The `verify.py` script (included in this repo) performs the following checks:

1. **Schema validation:** every line parses as valid JSON with the required fields for its event type.
2. **Temporal ordering:** events are in strictly ascending `ts_utc` order.
3. **Entry-exit pairing:** every `exit` event has a matching `entry` via `ref_entry_event_id`, and vice versa (no orphan entries without exits, except for currently open positions).
4. **Fee recomputation:** `entry.fee_btc == max(0.0001, min(0.0003, 0.125 * entry.exec_btc))` for each entry.
5. **L2 recomputation:** `entry.l2_btc == max(0, entry.mark_price - entry.exec_btc)` for each entry; analogous for exits.
6. **IM recomputation:** `entry.im_btc == max(0.10, 1.15 - 1/entry.x)` for short CALL.
7. **PnL recomputation:** for each (entry, exit) pair: `pnl_gross = entry.exec_btc - exit.exec_btc` and `pnl_net = pnl_gross - (entry.fee + entry.l2 + exit.fee + exit.l2)`. Compared against the declared `exit.pnl_gross_btc` and `exit.pnl_net_btc`. Tolerance: 1e-10 BTC (floating-point epsilon).
8. **Capital constraint:** at no point in the timeline does the sum of `im_btc` of open positions exceed 9.6 BTC.
9. **Event ID determinism:** `event_id == sha256(type + "|" + instrument + "|" + ts_utc + "|" + horizon)[:16]` for each event.

Output: `OK — N events, M completed trades, 0 discrepancies` or a list of failed checks with line numbers.

---

## Step 4 — Verify blockchain timestamp (optional)

If the `opentimestamps-client` is installed:

```bash
ots verify events.jsonl.ots
```

Expected output: `Success! Bitcoin block NNNNNN attests existence as of YYYY-MM-DD`.

This proves that the `events.jsonl` file (with its specific SHA-256 hash) existed at or before the timestamp anchored in the Bitcoin blockchain. Combined with the append-only property from Step 2, this means no events could have been inserted retroactively before that anchor point.

Note: OTS proofs are generated weekly. Events between two weekly anchors are covered by the SSH signatures (Step 1) but not yet by a blockchain timestamp. The next weekly anchor will cover them.

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
