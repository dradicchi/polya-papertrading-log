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

---

## 2026-04-18 (session 54): Daily entry cap per bucket

### Affected window

- **Start:** 2026-04-13 21:41 UTC (first entry of paper trading v2)
- **End:** 2026-04-18 (fix deployed; exact UTC timestamp visible in
  the commit that introduces the `rejected_daily_cap` event type)
- **Affected entries:** 95 of 159 entries in the window (~60%) were
  entries in excess of the cap that the canonical backtest applies
  per UTC day per t-bucket per horizon. Count measured at 2026-04-17
  22:00 UTC; the final number at cutover may shift by a handful of
  entries added in the intervening cycles.

### What was wrong, in plain language

The published track record comes from a backtest in which only one
decision window per UTC day exists: the strategy looks at the universe
once, ranks the eligible contracts inside each (horizon × time-to-expiry
bucket), and enters the top candidates of that single ranking. This
implicitly caps the number of new entries per day per bucket at the
strategy's selectivity parameter.

The paper trader, by contrast, runs every minute (1,440 cycles per UTC
day). Each cycle independently selects its top candidates from the
candidates eligible *at that minute*. Without an explicit daily cap,
the same bucket could absorb many more new entries over the course of
a day than the backtest ever would. In particular, when the underlying
moves and a fresh wave of contracts becomes eligible, multiple cycles
in a row can each add new positions to the same bucket — far above the
selectivity that the backtest enforces by construction.

The consequence is *capital dilution*, not bad picks. Every individual
entry was eligible under the strategy's signal rule; the issue is that
**aggregating dozens of entries per bucket per day inflated the peak
simultaneous initial margin (peak IM)** by roughly 2–4× versus what the
canonical backtest would consume in the same regime. ROI = PnL / AUM
falls when the denominator inflates, even if the numerator (PnL per
trade) stays roughly the same.

The pricing of every individual contract was correct. The selection
criterion of every individual entry was correct. The miss was a
capacity-control rule that exists implicitly in the backtest (because
it has only one decision window per day) but had not been ported
explicitly to the multi-cycle paper trader.

### Quantification

Of 159 entries in the affected window:

- **64 entries (~40%)** would have been admitted under the cap as well
  — these are within the per-day per-bucket selectivity that the
  backtest enforces.
- **95 entries (~60%)** were in excess of that cap.
- The excess concentrates in the daily horizon's `long` bucket: a
  single UTC day saw 21 entries in that one bucket alone.

The excess entries were all real positions priced from real market
quotes. Their realized P&L is recorded in `events.jsonl` and is
included in every reported performance metric for the affected window.
**No revisions are made to the existing log.**

### Fix applied

A daily cap on new entries per (horizon, t-bucket, UTC day) was added
to the entry logic. The cap is keyed off the same single source of
truth used by the backtest: a single configuration table that both the
backtest scripts and the paper trader import. The backtest file
contains an `assert` that fails at import time if the cap value
diverges from the backtest's per-day selectivity — preventing future
silent drift between the two pipelines.

The cap is **bucket-scoped and horizon-scoped** — three separate
counters per UTC day:

- monthly × {short, medium, long}
- weekly × {short, medium, long}
- daily × {short, medium, long}

Each counter is independent. Reaching the cap in one bucket does not
affect any other bucket or horizon.

The counter is queried from the database at the start of each cycle
and incremented in memory as new entries are admitted within that
cycle, so multi-cycle execution within the same day does not race
against itself. The counter resets naturally at 00:00 UTC because the
query keys on the entry's UTC date.

**Reentries count against the cap.** A reentry on the same instrument
(allowed for some horizons under a separate premium-rebound rule) is
a new `paper_trades` document and consumes one slot toward the daily
cap exactly like a first entry.

When the cap blocks a candidate, the rejection is recorded as a
`rejected_daily_cap` event in `events.jsonl`, with the instrument,
horizon, bucket, current count, and cap value — making the constraint
auditable end-to-end.

### Going forward

All entries from the cutover commit (2026-04-18) onward are subject
to the daily cap. The cap value matches the backtest's per-day
per-bucket selectivity exactly; the assert in the backtest module
enforces that the two cannot drift apart again.

This is the **mechanic alignment** counterpart to the universe
alignment of session 48 — the paper trader and the backtest now share
the same selection rule *and* the same capacity rule, while preserving
the paper trader's higher-cadence execution.

### Why the gap existed

When the paper trader was promoted from monthly-only (v1, daily
cadence) to multi-horizon (v2, 1-minute cadence) on 2026-04-13, the
selectivity rule was ported from the backtest as "top-K per bucket"
without an explicit per-day boundary. In the daily-cadence v1 setting,
"per cycle" and "per day" coincide, so the issue did not surface. In
the 1-minute v2 setting, they no longer do.

The diagnostic work is in session 54. The decision to cap and the
empirical justification for the specific cap value are recorded in
the research repo's session logs (proprietary).

### How to verify

- Search `events.jsonl` for the new event type:

```bash
grep '"type":"rejected_daily_cap"' events.jsonl | head
```

- Each such event carries `horizon`, `t_bucket`, `cap`, and
  `count_today` fields. After the cutover, no more than `cap` entries
  with the same `(horizon, t_bucket, ts_utc[:10])` should appear in
  `events.jsonl`.

- The historical excess can be reproduced from the published log: for
  every UTC day and every (horizon, t_bucket) combination prior to the
  fix timestamp, count the `entry` events; days where any
  (horizon, t_bucket) cell exceeds the cap are the affected days. The
  sum of (count − cap) across all such cells is 95.

---

## 2026-04-19 (session 55): Exit pricing convention — optimistic vs pessimistic scenarios

### Affected window

- **Start:** 2026-04-13 21:41 UTC (first entry of paper trading v2)
- **End:** ongoing (this is a reporting change, not a fix to the paper
  trader itself)
- **Affected entries:** all 110 closed trades to date, and every future
  closed trade. No entry or exit in `events.jsonl` is modified.

### What this is (and what it is not)

This is **not a correction of a bug** in the paper trader. The paper
trader's exit logic is unchanged. This is a **transparency disclosure
about the accounting convention** used when computing P&L for closed
trades.

### The convention, made explicit

From day one, the paper trader has recorded the execution price of
every exit as the Deribit `mark_price` at the time of the exit
decision. Equivalently: every exit event has
`exec_btc == mark_price` and `l2_btc == 0` on the close leg.

This is a specific modeling choice with a specific implication:

> "The P&L reported assumes we close each short position at the mid
> / mark price, with zero execution cost on the close leg."

In real execution, closing a short option position requires buying the
contract back — typically by hitting the ask (market buy) or placing a
limit order at the mid with uncertain fill rate. The `mark_price`
convention is therefore an **optimistic** baseline: it prices the
close at the theoretical fair value, not at the price a market buy
would actually pay.

This convention was implicit in the codebase. It had not been
explicitly documented in the published performance numbers.

### Quantification in the window to date

For the 110 closed trades in the current window, the gap between the
optimistic (mark) convention and a pessimistic (best ask) scenario is:

- **Daily**: 92 trades, +29% adjustment to reported P&L
- **Weekly**: 14 trades, +6% adjustment
- **Monthly**: 4 trades, +4% adjustment (low-n, noisy)
- **Combined**: 110 trades, **+28.9%** adjustment

The adjustment applies only to exits where the strategy actively buys
back the position (`alpha_exit` and `expiry_guard` exit reasons).
Trades that expire OTM naturally require no buy-back and are not
adjusted. In the current window, no position has reached natural OTM
expiration yet, so the adjustment applies to 100% of closed trades.

This is a 6-day window. The adjustment percentage may shift as the
sample grows, especially once natural OTM expirations begin to appear
in the monthly and weekly horizons (which would not contribute to the
adjustment and would dilute the combined percentage).

### What changed

Starting with the weekly report for `2026-W16` and every report
thereafter, a new section — **"Cenários de execução no fechamento"**
— appears in the published report. It shows two numbers side by side
for each horizon:

- **PnL mark (optimistic)** — the existing convention, unchanged
- **PnL ask (pessimistic)** — exits re-priced as if every buy-back
  paid the full best ask, for trades that require a buy-back

Real-world execution — limit orders at the mid with fallback to
market buy, or patient splitting across the book — lands somewhere
between these two. The purpose of reporting both is to make the range
explicit, rather than implicitly baking the optimistic scenario into
the headline number.

### No retroactive modification

Every previously published P&L number, Sharpe ratio, or ROI stands.
They were all computed under the optimistic (mark) convention. They
were not wrong in a bug sense — they were computed exactly as
documented in the code. What was missing was the disclosure that the
convention is optimistic.

The underlying `events.jsonl` log is untouched. The fields needed to
reconstruct any pricing scenario (`best_bid`, `best_ask`, `mark_price`
at entry and exit) have always been recorded and are in the log
verbatim. Any third party can apply their own execution assumption
and reproduce either scenario end-to-end.

### Why this matters for the track record

The direction of distortion is consistent across all 110 trades: the
optimistic convention overstates realized P&L by the amount of the
close-side spread. A reader of the published report who did not know
about the convention would reasonably interpret the headline P&L as
"the result after execution costs" — which is true on the entry side
(entries are recorded at `bid_price`, the short-side execution price)
and optimistic on the exit side.

The pessimistic scenario in the new section places a floor under the
reader's uncertainty: **the realized result cannot be worse than the
pessimistic scenario, unless the actual market buy paid above the
best ask at the time of the exit decision** — which is a liquidity
event that would be observable separately.

---

## 2026-04-19 (session 55): Backtest L2 convention — pessimistic scenario

### What is being disclosed

The published canonical backtest numbers — the `+131.6% / +15.9% / +26.8%` per-year ROI baselines for daily / weekly / monthly in bear holdout — are computed under a specific L2 (bid-ask spread) convention. This disclosure documents (a) what that convention actually measures, (b) why it is **optimistic** for a taker-style execution, and (c) a parallel "pessimistic" scenario calibrated empirically.

### The canonical convention, made explicit

For every trade in the backtest, L2 is computed as:

    L2_total = 2 × |price_trade − mark_price|

Where `price_trade` is the actual historical execution price in `options_trades` and `mark_price` is Deribit's theoretical fair value at the time of that trade.

This captures **the effective cost paid by the historical trader**. Most trades in an active option book execute *inside* the quoted bid-ask spread — price improvement, limit orders filled by makers, etc. The quantity `|price − mark|` is typically smaller than the half bid-ask spread. Doubling it gives a reasonable proxy of what that individual trader paid in total friction, averaged across direction.

### Why this is optimistic for a "taker" strategy

The Polya strategy, in live execution, can operate on a spectrum:

- **Maker-like** — post limit orders at/near the mid, wait for counterparty to cross. Low L2 cost, uncertain fill rate. The canonical convention approximates this.
- **Taker-like** — cross the spread on both legs: hit the bid on entry (sell short to the best-bid price), hit the ask on exit (buy back at the best-ask price). Maximum speed, full spread paid on both sides.

The canonical backtest does **not** decide which mode. It inherits whatever the historical trades in `options_trades` looked like — mostly maker-like with some price improvement. This leaves the reader unaware that the same strategy run as a pure taker would face higher L2.

### Empirical calibration of the taker scenario

For each horizon we measured a multiplier α such that:

    L2_pessimistic = α × L2_canonical

α was calibrated from **the bid-ask full spread actually observed in the order book**, via two data sources:

| Horizon | α (median) | n  | Source                              |
|---------|-----------:|---:|-------------------------------------|
| Monthly | **2.19**   | 411 | `options_snapshots` (book quotes)   |
| Weekly  | **1.84**   | 157 | `options_snapshots` (book quotes)   |
| Daily   | **1.66**   | 129 | Paper trading entries (book quotes at execution time) |

**Daily source note:** the order-book snapshot cron runs once per day and typically misses daily-expiry contracts (which are created and expire between two snapshot runs). We used the paper trader's recorded `best_bid` and `best_ask` at entry time instead — 129 entries across the first 6 days of paper trading. This is a smaller sample than the monthly/weekly α values and is subject to selection (only contracts the paper trader entered, not the full universe).

The α values are the **median ratio** of observed full bid-ask spread to the canonical `2 × |price − mark|` over all matched (instrument, date) pairs. We used median (robust to outliers) rather than mean — the distribution of α has a long right tail driven by thin-book instruments.

### Quantitative impact on the canonical baselines

Applied to each horizon's canonical backtest (holdout OOS bear, 2025-09-07 → 2026-03-28, 757 / 106 / 209 trades respectively):

| Horizon | Canonical ROI/yr | Pessimistic ROI/yr | Δ (pp/yr) |
|---------|-----------------:|-------------------:|----------:|
| Daily   | **+131.6%**      | **+124.0%**        | **−7.6**  |
| Weekly  | **+15.9%**       | **+13.8%**         | **−2.1**  |
| Monthly | **+26.8%**       | **+25.5%**         | **−1.3**  |

Daily is the horizon most sensitive to this correction because premiums are smaller — L2 is a larger fraction of gross P&L. Monthly and weekly have large gross premiums relative to the spread, so the correction is marginal.

**Win rate, sample size, and AUM are unchanged** — only L2 is scaled. α does not affect which trades are winners or losers; it only scales the execution cost.

### Why this is a disclosure, not a bug fix

The canonical numbers are not wrong. They describe performance *if the strategy trades like the historical traders in the book did* — which is a defensible baseline (maker-like, with price improvement). The pessimistic scenario describes a different, equally defensible baseline (taker, maximum speed).

Real execution falls between these two, closer to one end or the other depending on:

- Contract liquidity (thinner book → closer to pessimistic)
- Execution patience (willingness to wait for limit fills → closer to canonical)
- Market regime (volatility spikes widen spreads, push toward pessimistic)

### What changed in the repository

- Canonical backtest scripts (`backtest_strategy_v2.py`, `backtest_weekly_v2.py`, `backtest_strategy_daily_v2.py`) now accept a `BACKTEST_L2_ALPHA` environment variable. Without the variable (default α=1.0), they reproduce the canonical numbers exactly. With `BACKTEST_L2_ALPHA=α`, L2 is scaled by α globally.
- The canonical numbers published in `README.md` and prior reports remain unchanged. The pessimistic scenario is presented in parallel for context.
- Weekly reports henceforth reference both (canonical as "headline", pessimistic as "lower bound").

### Caveats of the calibration

- **Small temporal window:** snapshot data is concentrated in 2026-02-28 → 2026-04-09 (the last ~40 days of the holdout). α values represent spread regime during that window and may not extrapolate to the earlier 160 days.
- **Daily α is especially small-sample:** n=129 from 6 days of live paper trading. As the paper trader accumulates more entries, this number will be revised.
- **α ignores variance:** the median α is a point estimate. The full distribution has a long right tail (p90 ≥ 6 for monthly), meaning individual contracts can face much higher spread than the median.
- **Sharpe ratio not recomputed under α:** the current Sharpe in the canonical output is calculated on gross P&L (y-units), not on net BTC P&L. Recomputing Sharpe under the pessimistic scenario would require a refactor; it is a future refinement.
- **α is not dynamic within the backtest window:** we apply a single horizon-level α to every trade, which is an aggregate approximation. Trade-level α (from paired buy/sell trades in narrow time windows around each backtest trade) would be more rigorous but costs implementation time without changing the order-of-magnitude result here.

### Reproducibility

The calibration scripts are in the main (private) repository:

- `check_l2_asymmetric_coverage.py` — measures viability of reconstructing bid/ask from trade `direction` labels. Gate: ≥70% coverage of the operational universe. Result: **95.7%** passed.
- `check_bid_ask_proxy_validation.py` — validates direction-based proxy against snapshots. Result: strong bid/ask correlation (0.999) but the proxy does not capture the intraday bid-ask spread separation; pivoted to direct snapshot measurement.
- `check_l2_alpha_factor.py` — measures α per horizon from snapshot full spread vs `2 × |price − mark|` in the same (instrument, date) pairs.

Anyone can reproduce the α values from `options_snapshots` and `options_trades` in the main-repo database dump.
