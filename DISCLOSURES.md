# Methodological Disclosures — Polya Paper Trading v2

This document records methodological corrections applied during the
public paper trading run. The paper trading log (`events.jsonl` and
`positions/`) is preserved as-is — including data collected before
each correction. This file is the audit trail for what was wrong, when
it was found, and what was fixed.

The principle: transparency over silent revision. Every entry in
`events.jsonl` is real; this document tells you which subset was
collected under fixed-since methodology and which under since-corrected
methodology.

The strategy ruleset itself is proprietary and not published in this
repository (see `README.md`, "Strategy rules"). The disclosures below
describe *that* a methodological gap existed, *when* it was active,
and *what was the impact* — without revealing the specific filter
values or model parameters.

---

## 2026-04-15 (session 48): Universe alignment

### Affected window

- **Start:** 2026-04-13 21:41 UTC (first entry of paper trading v2)
- **End:** 2026-04-15 ~22:00 UTC (all four corrections deployed)
- **Affected entries:** ~87 (all entries before commit `<B188-commit>`)

### What was wrong, in plain language

Four progressively-tightened gaps in the real-time scoring layer
caused the paper trading universe to diverge from the canonical
universe used in the backtest that produced the published track
record. The gaps did not affect the *pricing* of any contract — they
affected *which contracts* were considered for entry, and *which model*
was used to evaluate them.

The four gaps were:

1. **Moneyness filter not enforced.** The strategy is short OTM CALL
   (publicly stated in `README.md`), but the real-time scorer did not
   reject in-the-money or extreme deep-out-of-the-money contracts
   before scoring. As a result, a small number of positions were
   opened in moneyness ranges where the strategy was not designed to
   operate.
2. **Cross-universe scoring.** Each model in the backtest is trained
   on a single Deribit `settlement_period` (one of `day`, `week`,
   `month`). The real-time scorer classified contracts into horizons
   by their time-to-expiry instead of by their `settlement_period`.
   As a result, contracts of one settlement_period were sometimes
   scored by a model trained on contracts of a different
   settlement_period.
3. **Operational filters not enforced.** The backtest applies
   horizon-specific operational filters on top of the model's
   training range (a moneyness ceiling, a maximum time-to-expiry,
   and a near-expiry guard). The real-time scorer was using only
   the model's calibration range, which is wider. The strategy was
   therefore considering contracts that the backtest excludes.
4. **Filter values were duplicated** across the backtest scripts and
   the paper trader rather than read from a single source of truth.
   Items 1–3 above were all symptoms of this duplication: changes to
   the backtest filters had not been propagated to the paper trader.

### Quantification of the affected entries

Of the 87 entries in the affected window:

- **62 entries (71%)** were already correctly classified — the
  contract's `settlement_period` matched the horizon under which it
  was entered. These are unaffected by the cross-universe correction.
- **25 entries (29%)** were cross-universe. Specifically:
  - 16 entries booked under the `daily` horizon were `week`
    contracts
  - 5 entries booked under `weekly` were `month` contracts
  - 4 entries booked under `weekly` were `day` contracts
- A small number of entries (single digits across all horizons) were
  outside the operational moneyness range that the backtest enforces.

### Realized P&L impact: zero

All 12 closed trades as of 2026-04-15 are correctly-classified
`daily` × `day` matches. **No closed trade is from a cross-universe
or out-of-range entry.** The realized track record up to the
correction date is clean.

### Open positions at fix time

Approximately 25 open positions were cross-universe at the moment of
the fix. **They were not manually closed.** Two reasons:

1. The trades themselves are real and economically valid contracts —
   only their *interpretation* (which model selected them) is wrong.
   The underlying option pricing is universal across horizons.
2. They will resolve naturally via the strategy's existing exit logic
   (deterministic, rule-based — see `README.md`).

### Going forward

All entries from 2026-04-15 ~22:00 UTC onward operate under the
canonical universe. The four gaps above are closed by code-level
fixes in the research repository and a single shared source of truth
for filter values across both the backtest and the paper trader.

The first weekly report covering the affected window will include a
methodological footnote pointing to this document; subsequent reports
will not.

### Capital pot resize (related housekeeping)

Independently of the universe alignment above, on 2026-04-15 the
capital pot was resized from **9.6 BTC** (the value listed in the
prior version of `README.md`) to **20 BTC**, after observing that the
realized fill rate during the first 28 hours of operation was higher
than the original projection. The resize is conservative: the
projected steady-state initial margin requirement was below 16 BTC
and 25% buffer takes it to 20.

This is not a methodological correction — the original 9.6 BTC was
not "wrong", just smaller than what the operational fill rate
required. It is documented here for completeness because `README.md`
mentions the pot size as a public fact.

### Why the gaps existed

The real-time scoring infrastructure was created shortly before the
paper trading go-live. The author copied the model's training range
from the calibration metadata but did not port the *operational*
filters from the backtest scripts (which were thought of as the
"strategy layer", separate from "scoring"). In paper trading v2, the
scorer is also the eligibility gate — there is no separate strategy
layer between scoring and entry — so the missing operational filters
silently degraded the universe.

The gaps were detected during a routine diagnostic of the first 28
hours of paper trading data, not by a production failure or by an
external audit.

### Audit trail

- Universe corrections: backlog items B183, B184, B186, B188
  (internal references)
- Conceptual principle: the canonical universe and the selection /
  exit rules are shared between the backtest and the paper trader;
  the paper trader is allowed to sophisticate only the *operational
  mechanics* (e.g., the cadence of scoring cycles), not the rules
  themselves
- 495 unit tests passing as of 2026-04-15
- Test coverage for the universe alignment: included

### How to verify (independently of the research repo)

Anyone auditing this repo can cross-check the disclosures against
`events.jsonl`:

- The affected window is `entry` events with
  `ts_utc < 2026-04-15T22:00:00Z`
- For each entry, the contract's `settlement_period` can be retrieved
  via Deribit's public API:
  `https://www.deribit.com/api/v2/public/get_instrument?instrument_name=<name>`
- Compare the returned `settlement_period` (`day`, `week`, `month`)
  against the `horizon` field in the entry. The expected mapping is
  `day` → `daily`, `week` → `weekly`, `month` → `monthly`. Mismatches
  are the cross-universe entries.
- The number of mismatches in the affected window matches the count
  reported in this document (25 of 87).

### Pot size verification

The pot size at any moment can be inferred from `events.jsonl` by
summing the `im_btc` field of all open positions and adding the
`im_available_btc` field of the most recent `rejected_no_capital`
event (if any). The resize from 9.6 → 20 BTC will be visible as a
discontinuity in the maximum committed initial margin around
2026-04-15.

---

## 2026-04-16 (session 50): Minimum bid filter

### Affected window

- **Start:** 2026-04-13 21:41 UTC (first entry of paper trading v2)
- **End:** 2026-04-16 ~01:30 UTC (fix deployed)
- **Affected entries:** 2 daily entries with bid < 0.0003 BTC

### What was wrong, in plain language

The paper trader entered positions where the option premium received
(the bid price) was so small that the exchange's fixed trading fees
consumed all the possible profit. These trades were **guaranteed to
lose money from the moment they were opened**, regardless of how
favorably the underlying moved.

The issue arises because Deribit charges a fixed fee of 0.0001 BTC
per leg (entry + exit = 0.0002 BTC minimum). When the strategy's
exit rule captures ~90% of the entry premium, a trade with a bid of
0.0003 BTC produces a gross profit of ~0.00027 BTC — which is barely
above the fixed fees and does not cover the additional spread cost
(L2). Below approximately 0.00022 BTC bid, the trade is structurally
unprofitable even with perfect execution.

The backtest does not exhibit this problem because it simulates
execution at the mark price (the option's mid-market theoretical
value) and accounts for the bid-ask spread as a separate cost line.
In the live market, the bid (what the seller actually receives) can
be 30–50% lower than the mark for deep out-of-the-money options near
expiry — a gap that the backtest's cost model does not generate at
the individual trade level.

### Quantification

Of 108 entries in the affected window:

- **2 entries** had bid prices below the new threshold (0.0003 BTC):
  - `BTC-15APR26-78000-C` (daily): bid=0.0003, mark=0.000609,
    PnL gross=+0.000271, costs=0.000509, **PnL net=−0.000238 BTC**
  - `BTC-16APR26-79000-C` (daily): bid=0.0005, mark=0.000761,
    PnL gross=+0.000452, costs=0.000461, **PnL net=−0.000009 BTC**
- Both trades were closed via alpha-exit with **positive gross P&L**
  but **negative net P&L** after costs.
- Combined net loss: −0.000247 BTC (0.6% of total realized P&L).

### Fix applied

A minimum bid filter (`BID_MIN_BTC = 0.0003`) was added to the entry
logic. Trades with a bid price below this threshold are silently
rejected before execution. The threshold is ~35% above the
theoretical break-even (0.00022 BTC) to provide a margin of safety.

This filter is an **operational safeguard** specific to the paper
trader (and future production systems). It does not exist in the
backtest, which uses a different execution model. It applies equally
to all three horizons (monthly, weekly, daily), though in practice
it only binds for daily contracts — monthly and weekly options
typically have bid prices well above the threshold.

### Going forward

All entries from 2026-04-16 ~01:30 UTC onward are subject to the
minimum bid filter. Contracts with insufficient premium to cover
fixed execution costs will not be entered.

### How to verify

The two affected trades are visible in `events.jsonl` as `entry` +
`exit` event pairs with the instruments listed above. Their
`exec_btc` field (= bid at entry) is below 0.001 BTC, and their
exit events show negative `pnl_net_btc`. No future entries should
have `exec_btc` below 0.0003 BTC.
