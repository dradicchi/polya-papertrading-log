# Polya Paper Trading Log

Public, tamper-evident track record of a systematic short-volatility strategy on BTC inverse options (Deribit).

This repository is the **source of truth** for the paper trading phase of Polya Technologies. It contains every simulated entry, exit, and resulting P&L, recorded in real time from public market data. The model behind the trades is proprietary and is **not** disclosed here — the purpose of this log is to let third parties (investors, auditors) independently verify the realized performance of the strategy without depending on Polya's own reports.

---

## TL;DR for auditors

1. Every event in `events.jsonl` is appended when it happens. Lines are never rewritten.
2. Every commit in this repo is cryptographically signed with an Ed25519 SSH key published on the author's GitHub profile. GitHub displays a **Verified** badge on each valid commit.
3. The repository history is append-only. Force-push is disallowed by policy. Any modification to past commits would break the signature chain and be visible in any clone made before the tampering.
4. Weekly snapshots are anchored to the Bitcoin blockchain via [OpenTimestamps](https://opentimestamps.org/), giving each anchored point an unforgeable timestamp independent of GitHub and the author.
5. All event prices can be cross-checked against the Deribit public order book API at the timestamp declared in each event. No insider data, no aggregates, no model output — only externally observable market state.
6. To independently verify the full PnL from the raw event stream, see [`VERIFY.md`](./VERIFY.md).

---

## What this log records

Three simultaneous models operating on Deribit BTC inverse options, CALL-only, 1 contract per signal:

| Horizon | Instruments | Hold duration |
|---|---|---|
| **Monthly** | `BTC-DDMMMYY-SSSSS-C` with t ≤ 60 days | ~22 days |
| **Weekly** | Same family, t ∈ [1, 21] days | ~10 days |
| **Daily** | Same family, t ∈ [0.5, 4] days | ~1–3 days |

The three models operate over a single shared capital pot of **9.6 BTC** (the "Floor" level from the strategy's capacity analysis, including a conservative MtM buffer). All positions are short — the strategy collects option premium when the model identifies instruments that are structurally overpriced relative to a theoretical fair value.

**What you will NOT find here:** the model that decides which contracts to enter. No signal values, no fair prices, no regression coefficients, no predictor data. The audit scope is: *"given that a trade was opened, is the recorded execution consistent with the public book at that timestamp, and is the final P&L correctly computed?"*. That question is answerable from the data in this repo plus public Deribit market data.

---

## Strategy rules

The complete operational ruleset (entry criteria, exit logic, position sizing, stopping rules) was frozen on **2026-04-12** in an internal document before the go-live. The rules are proprietary and are **not published** in this repository.

What can be stated publicly:

- **Positions are short CALL only** (the strategy collects option premium). This is directly observable from the events.
- **Sizing is 1 contract per signal**, invariant across all three horizons. This is directly observable from the events.
- **Capital pot is 9.6 BTC.** Entries are rejected when the pot is fully committed (logged as `rejected_no_capital` events).
- **Exit rules are deterministic and rule-based** — no discretionary exits. The specific exit logic is proprietary, but the realized execution (entry price, exit price, exit reason, P&L) is fully logged and verifiable.
- **Stopping rules exist** and are monitored automatically. If triggered, a `pause` event is logged publicly with the affected horizon.
- **Rules are frozen for the duration of the test** (minimum 90 days). Any mid-period rule change would invalidate the out-of-sample claim and would be disclosed as a `correction` event in the log.

The audit question is not "are the rules good?" — it is "given the rules (whatever they are), does the recorded track record accurately reflect what the strategy produced in forward, out-of-sample conditions?". That question is fully answerable from this repository.

---

## Repository structure

```
polya-papertrading-log/
├── README.md                        (this file)
├── SCHEMA.md                        (full definition of event fields)
├── VERIFY.md                        (step-by-step audit instructions)
├── LICENSE                          (CC-BY-4.0 for data)
├── events.jsonl                     (FONTE DE VERDADE — append-only event stream)
├── events.jsonl.ots                 (OpenTimestamps proofs, refreshed weekly)
├── positions/
│   └── open.json                    (live snapshot of currently open positions)
├── sessions/
│   └── YYYY-MM-DD.md                (human-readable daily summary)
└── reports/
    └── YYYY-WW.md                   (weekly performance report)
```

- `events.jsonl` is the canonical machine-readable source of truth. Every other file in the repo is a view of it. If any file disagrees with `events.jsonl`, `events.jsonl` is correct and the other file has a bug.
- `positions/open.json` is **rewritten** with each event (it is a projection, not history). Its content should always be reproducible from replaying `events.jsonl`.
- `sessions/` and `reports/` are generated artifacts that summarize what happened. They are not authoritative — they are convenience renderings.

---

## Signing and verification

- **Signing key:** Ed25519 SSH key with fingerprint `SHA256:Xp/CnXQhSmdpBRLWhoOXENkBc3FRkMIJeOBFh+XJKUM`
- **Publisher:** `github.com/dradicchi` — the key is published on the GitHub profile both as Authentication Key and Signing Key. Anyone can fetch the public key via `https://github.com/dradicchi.keys` and verify it matches.
- **Signing format:** Git SSH signing (native support since Git 2.34). Run `git log --show-signature` to see `Good "git" signature for ...` for every commit.
- **Git hook policy:** no force-push to `main`, no rewriting of published commits. A policy cannot be enforced technically without GitHub branch protection (which is a paid feature); instead, we rely on the clone-once-verify-later discipline: any party that clones this repo at any point has a local copy whose hashes must match any future re-clone. Divergence is detectable.
- **Blockchain anchoring:** `events.jsonl.ots` is an OpenTimestamps proof that the hash of `events.jsonl` at a given commit existed on or before a specific moment in time, as confirmed by inclusion in a Bitcoin block. See `VERIFY.md` for the command to verify it.

---

## Disclaimers

1. **No real trades.** This is a paper trading log. No capital is at risk; no orders are sent to Deribit; no positions exist. Every event is a simulation computed from public market data observed at the declared timestamp.
2. **Execution fidelity is realistic-pessimistic.** Entries are simulated at the `best_bid` of the Deribit public book (worst plausible sale price), exits at the `best_ask` (worst plausible repurchase price). The full bid-ask spread is paid on each trade. Deribit taker fees are applied to every opening and closing leg. The resulting P&L is therefore a conservative lower bound on what a real execution could achieve — in practice, an institutional execution would typically fill somewhere in the spread and pay maker fees on at least some legs.
3. **No tax, no funding, no settlement risk.** The strategy is all-option; no perpetual hedge. Settlement in BTC-denominated inverse contracts. No USD conversion in the P&L. No tax computation. No counterparty or exchange risk modeled.
4. **Model NOT disclosed.** The scoring model that decides entries is proprietary. This repo contains its outputs (which trades to open), not its internals. The audit is "did the declared trade execute consistently with the public book?", not "is the model's decision correct?".
5. **Past performance ≠ future results.** Standard. Paper trading results are specific to the regime observed during the test period. Extrapolating to a different market regime is a research question, not a certainty.
6. **License:** event data is CC-BY-4.0 — free to use, cite, and redistribute with attribution. The scoring model is not part of this license and remains proprietary.

---

## Contact

Daniel Radicchi — `github.com/dradicchi`

For audit inquiries: open an issue on this repository.

For business inquiries: (to be updated when Polya Technologies legal entity is incorporated).
