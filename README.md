# Polya Paper Trading Log

Public, cryptographically verifiable paper-trading record of a systematic short-volatility strategy on Bitcoin inverse options (Deribit). Every trade, every decision, every model output is appended to this repository as it happens — no retroactive edits, no marketing reconstructions, no selective disclosure.

[Polya Technologies](https://polyatechnologies.com) · [Founder](https://linkedin.com/in/daniel-radicchi) · [Contact](mailto:contact@polyatechnologies.com)

---

## What this is

This repository is the operational log of Polya's paper-trading phase. It is **not** a backtest, **not** a marketing site, and **not** a curated highlight reel. It is the actual record of trades placed (in paper-trade mode) against live Deribit order books, recorded as the trades happen.

The purpose is to make Polya's track record **independently verifiable** before live capital is deployed, and to make any future track record **resistant to retroactive editing**.

## Why this exists

In quantitative finance, track records are typically disclosed in aggregated form (monthly NAV, annual returns) by the fund itself, with no underlying trade-level data and no third-party verification that the disclosed numbers correspond to actual executions. The investor relies on the fund's word, the fund's auditor's word, and SEC registration where applicable.

Polya Technologies is an **AI-assisted proprietary trading firm** — no external limited partners, no asset management business — so we have no regulatory obligation to disclose anything. We chose to publish the full trade-level record anyway, with cryptographic guarantees of sequence, time, and author integrity, because:

1. We are deploying capital from equity investors who deserve to verify the operation, not just trust the founder's representation
2. A track record that cannot be retroactively edited is a stronger guarantee than any conventional audit
3. The cost of operating in this open mode is low; the credibility premium is high

---

## Current state

**76 days since go-live** · Apr 13 → Jun 28, 2026 · Capital pot: 20 BTC

### Architecture: parallel instances

The paper-trading system runs several parallel parameter configurations to isolate the operational effect of strategy parameters and preserve experimental optionality without losing the historical baseline. **Each instance publishes its own reports** under `instances/<id>/reports/` (`weekly/` and `monthly/`); each report leads with the **cumulative-since-go-live** metrics, then the **cycle window**:

| Instance | Status | Reports |
|---|---|---|
| `canonical` | Active since May 9 | reference instance, no overrides — [weekly](instances/canonical/reports/weekly/) · [monthly](instances/canonical/reports/monthly/) |
| `full_overrides` | Active since May 9 | experimental config A — [weekly](instances/full_overrides/reports/weekly/) · [monthly](instances/full_overrides/reports/monthly/) |
| `partial_overrides` | Active since May 9 | experimental config B — [weekly](instances/partial_overrides/reports/weekly/) · [monthly](instances/partial_overrides/reports/monthly/) |
| `partial_clean` · `partial_k2_2pct` · `partial_k2_5pct` | Active since Jun 9 | short-call-spread trio, daily-only (control + 2%/5% hedge) — [clean](instances/partial_clean/reports/weekly/) · [k2-2%](instances/partial_k2_2pct/reports/weekly/) · [k2-5%](instances/partial_k2_5pct/reports/weekly/) |
| `legacy_v2.1` | Frozen on May 9 | original PT v2 baseline (includes the PM-001 window) — [weekly](instances/legacy_v2.1/reports/weekly/) · [monthly](instances/legacy_v2.1/reports/monthly/) |

### Performance snapshot — canonical instance, daily horizon

Cumulative since go-live (as of weekly cycle W07 · 354 daily trades):

- Annualized ROI on CEA: **+100.6%**
- Daily Sharpe ratio: **+9.59**
- Win rate: **90%**
- Max drawdown: **−1.1%** of CEA

_CEA (Capital Effectively Allocated) = peak simultaneous initial margin × 1.25 — the capital actually at risk (the metric previously labeled "AUM"; see [`DISCLOSURES.md`](DISCLOSURES.md))._

Reports refresh per closed cycle, **per instance** (see the table above). The live event streams are the per-instance logs under [`instances/<id>/events.jsonl`](instances/) — `instances/canonical/events.jsonl` is the canonical public benchmark. The root [`events.jsonl`](events.jsonl) is the **frozen `legacy_v2.1` baseline** (last event 2026-06-01) and is no longer the active source of truth for current headline metrics. The canonical pricing-and-execution stack runs without experimental overrides; the override instances are under live evaluation. _(The root `reports/` folder is likewise retired — the frozen `legacy_v2.1` baseline now lives under [`instances/legacy_v2.1/reports/`](instances/legacy_v2.1/reports/).)_

### Which file should I audit?

- **Active source of truth** — the per-instance event streams: `instances/<id>/events.jsonl`. The headline performance snapshot above comes from **`instances/canonical/events.jsonl`**.
- **Legacy baseline** — the root `events.jsonl` is the frozen `legacy_v2.1` stream (through 2026-06-01, includes the PM-001 window). Retained for continuity; not the active record.
- **Everything else** (reports, `positions/open.json`, sessions) is a generated view of these streams.

---

## What this log records

Three concurrent models operate on Deribit BTC inverse options (settled in BTC), short side, one contract per signal:

| Horizon | Instruments | Hold duration |
|---|---|---|
| **Monthly** | `BTC-DDMMMYY-SSSSS-C` with t ≤ 60 days | ~22 days |
| **Weekly** | Same family, t ∈ [1, 21] days | ~7 days |
| **Daily** | Same family, t ∈ [0.5, 4] days | ~1.5 days |

The strategies systematically capture the volatility risk premium by selling option premium when the pricing model identifies the market price as overstated relative to fair value, with early exit when the market converges to the model.

The pricing model, ranking heuristics, parameter values, and execution layer remain proprietary. **This repository does not disclose them.** It discloses what is necessary to verify that the trades happened, that the prices and volumes correspond to public Deribit data, and that the P&L computation is honest.

---

## Strategy rules

The complete operational ruleset (entry criteria, exit logic, position sizing, stopping rules) was frozen on **2026-04-12** in an internal document before the go-live. The rules are proprietary and are **not published** in this repository.

What can be stated publicly:

- **Positions are short CALL only** (the strategy collects option premium). Directly observable from the events.
- **Sizing is 1 contract per signal**, invariant across all three horizons. Directly observable.
- **Capital pot is 20 BTC** (resized from 9.6 BTC on 2026-04-15 — see [`DISCLOSURES.md`](DISCLOSURES.md)). Entries are rejected when the pot is fully committed (logged as `rejected_no_capital`).
- **Exit rules are deterministic and rule-based** — no discretionary exits. The specific exit logic is proprietary, but the realized execution (entry price, exit price, exit reason, P&L) is fully logged and verifiable.
- **Stopping rules exist** and are monitored automatically. If triggered, a `pause` event is logged publicly with the affected horizon.
- **Rules are frozen for the duration of the test** (minimum 90 days). Any mid-period rule change would invalidate the out-of-sample claim and is disclosed as a `correction` event in the log.

The audit question is not "are the rules good?" — it is **"given the rules (whatever they are), does the recorded track record accurately reflect what the strategy produced in forward, out-of-sample conditions?"**. That question is fully answerable from this repository.

---

## Verification — how to audit this repository

Six layers of cryptographic and methodological protection. The detailed step-by-step guide is in [`VERIFY.md`](VERIFY.md); the summary below describes what each layer proves.

### Trust layers

| Layer | What it proves | Strength |
|---|---|---|
| SSH-signed commits (Ed25519) | Events were authored by the holder of the signing key | Strong (cryptographic) |
| GitHub Verified badge | GitHub independently confirms each signature | Strong (independent verifier) |
| Append-only `events.jsonl` + git diff | No past events were edited | Strong (Merkle chain) |
| OpenTimestamps anchor | Events existed at or before the anchored Bitcoin block | Very strong (Bitcoin blockchain) |
| P&L recomputation (`verify.py`) | Declared performance matches raw event data | Deterministic (mathematical) |
| External price cross-check | Declared market state actually occurred on Deribit | Strongest (independent data source) |

No single layer is sufficient on its own. Together, they form a defense-in-depth that would require compromise of multiple independent systems (GitHub, Bitcoin blockchain, Deribit, any auditor's own clone) to defeat.

### Signing key

- **Ed25519 SSH key** with fingerprint `SHA256:Xp/CnXQhSmdpBRLWhoOXENkBc3FRkMIJeOBFh+XJKUM`
- Published on the author's GitHub profile as both Authentication Key and Signing Key
- Fetch with `curl -s https://github.com/dradicchi.keys`
- Git native SSH signing format (since Git 2.34); run `git log --show-signature` to verify

### What this audit proves — and does not prove

This audit proves:

- **Sequence integrity** (append-only): no event was inserted retroactively
- **Time integrity** (OpenTimestamps): events were recorded no later than the next weekly Bitcoin-anchored timestamp
- **Author integrity** (Ed25519): commits were made by the declared author
- **Computational integrity** (verify.py): declared P&L matches the raw event data deterministically
- **Market integrity** (Deribit cross-reference): declared prices and volumes correspond to public market data at the declared timestamps

This audit does **not** prove:

- The **trading model itself** is correct or profitable in expectation. Fair-value pricing, ranking, and execution heuristics remain proprietary and unverifiable from this repository.
- That **paper-traded execution will translate to live execution** at the same prices. Live deployment introduces additional frictions — order rejection, ask-side fills, queue priority — that paper trading does not model.
- This is **not an audit by a registered third-party auditor** under any regulatory regime. It is independent verification by anyone with access to a Git client and a few standard tools.

These limits are intentional: the repository discloses what an investor can verify independently, and clearly distinguishes **verification of operation** from **validation of strategy**.

---

## Repository structure

```
polya-papertrading-log/
├── README.md                  ← you are here
├── SCHEMA.md                  ← full definition of event fields
├── VERIFY.md                  ← step-by-step audit instructions
├── DISCLOSURES.md             ← methodological gaps, retroactive notes
├── LICENSE                    ← CC-BY-4.0 (data only; model is proprietary)
├── events.jsonl               ← LEGACY source (frozen legacy_v2.1 baseline, through 2026-06-01)
├── verify.py                  ← deterministic P&L re-computation script
├── instances/                 ← ACTIVE SOURCES OF TRUTH — per-instance event streams AND reports
│   └── <id>/
│       ├── events.jsonl        ← append-only event stream (canonical = public benchmark)
│       ├── timestamps/         ← OpenTimestamps proofs (Bitcoin-anchored) for this stream
│       └── reports/            ← weekly (W01…) + monthly (M01…), cumulative-first
├── timestamps/                ← OpenTimestamps proofs for the frozen legacy root stream — see VERIFY.md
├── positions/
│   └── open.json              ← live snapshot of currently open positions
├── sessions/                  ← human-readable daily summaries
├── reports/                   ← RETIRED (legacy baseline moved to instances/legacy_v2.1/reports/)
├── post-mortems/              ← operational incident records (PM-001, ...)
└── api_archive/               ← raw market data archive (auditor reference)
```

- The `instances/<id>/events.jsonl` streams are the canonical machine-readable source of truth (the root `events.jsonl` is the frozen `legacy_v2.1` baseline). Every other file in the repository is a view of these streams. If any file disagrees, the instance event stream is correct.
- `positions/open.json` is **rewritten** with each event (it is a projection, not history). Its content is reproducible from replaying the event streams.
- `sessions/` and `reports/` are generated artifacts — convenience renderings, not authoritative.
- `instances/` segregates the parallel parameter configurations: `canonical`, `full_overrides` and `partial_overrides` (introduced May 9, 2026), the `partial_clean` / `partial_k2_2pct` / `partial_k2_5pct` short-call-spread trio (introduced June 9, 2026), and the frozen `legacy_v2.1` baseline — seven streams in total.

---

## Operational transparency

We document operational incidents in [`post-mortems/`](post-mortems/) and methodological gaps in [`DISCLOSURES.md`](DISCLOSURES.md) rather than editing history retroactively.

### PM-001 — bear-to-bull mean-reversion event (May 2026)

The most notable incident to date: a short-window bear-to-bull mean-reversion event in early May 2026 that materially impacted the daily model's cumulative figures under the original PT v2 configuration. We diagnosed the structural cause, deployed an operational refinement on May 7–9, and now run the canonical post-refinement instance in parallel with the frozen pre-refinement record. Neither has been edited.

See [`post-mortems/PM-001-2026-05-02.md`](post-mortems/PM-001-2026-05-02.md) for the full incident report — context, mechanism, diagnostic process, decision, and outcome.

This is the standard we hold: **operational events are owned, not hidden.**

### Active methodological disclosures

Detected gaps during the run are documented in [`DISCLOSURES.md`](DISCLOSURES.md). Notable active item:

- **2026-04-15 universe alignment** (session 48): ~87 entries in the window 2026-04-13 21:41 UTC → 2026-04-15 22:00 UTC were affected by four progressively tightened gaps between paper trader and canonical backtest universe. Realized P&L unaffected; open positions were not manually closed; entries after the fix operate under the canonical universe.

---

## Disclaimers

1. **No real trades.** This is a paper trading log. No capital is at risk; no orders are sent to Deribit; no positions exist. Every event is a simulation computed from public market data observed at the declared timestamp.
2. **Execution fidelity — conservative entries, mark-price exits with a pessimistic scenario in parallel.** Entries are simulated at the `best_bid` of the Deribit public book (the worst plausible sale price for a premium seller). Exits are recorded at `mark_price`: headline P&L assumes a limit fill at mid with no spread paid on the closing leg — a model-consistent convention that measures the model's convergence to fair value. Every cycle report **also publishes a pessimistic `best_ask` scenario** (immediate market buy-back, full spread paid) alongside the mark scenario; real execution sits between the two depending on execution quality. Deribit taker fees are applied to every leg in both scenarios. **Headline figures in this README and in the reports are the mark scenario unless labeled otherwise.**
3. **No tax, no funding, no settlement risk.** The strategy is all-option; no perpetual hedge. Settlement in BTC-denominated inverse contracts. No USD conversion in the P&L. No tax computation. No counterparty or exchange risk modeled.
4. **Model NOT disclosed.** The scoring model that decides entries is proprietary. This repository contains its outputs (which trades to open), not its internals. The audit is "did the declared trade execute consistently with the public book?", not "is the model's decision correct?".
5. **Past performance ≠ future results.** Paper trading results are specific to the regime observed during the test period. Extrapolating to a different market regime is a research question, not a certainty. The four-instance architecture is designed to test parameter variations across regimes; it does not eliminate regime risk.
6. **Polya Technologies is a technology company.** We do not solicit investment, offer financial advice, or provide regulated financial services. This repository is a transparency artifact, not a solicitation.

---

## License

Event data in this repository is published under **CC-BY-4.0** — free to use, cite, and redistribute with attribution. The trading model, pricing layer, execution heuristics, ranking parameters, and parameter values remain proprietary intellectual property of Polya Technologies and are **not disclosed in this repository**.

---

## About Polya Technologies

Polya Technologies is an **AI-assisted proprietary trading firm** operating in Bitcoin derivatives. We design, calibrate, and operate our own quantitative models on a research-to-production stack built around an agentic AI pipeline. This repository is the public audit trail of our paper-trading phase — methodology proof before live capital deployment.

- Site: [polyatechnologies.com](https://polyatechnologies.com)
- Founder: [Daniel Radicchi](https://linkedin.com/in/daniel-radicchi)
- Stage: late pre-seed
- Contact: [contact@polyatechnologies.com](mailto:contact@polyatechnologies.com)
- Audit inquiries: open an issue on this repository
