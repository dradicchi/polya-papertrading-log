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

## 2026-04-19 (session 55 part 2): Sharpe daily methodology

### What changed

Prior weekly reports computed Sharpe daily with three conventions that
differed from the standard quant literature baseline and from the
internal research backtest:

1. The daily P&L series included **only days with trades** (excluded
   days with zero P&L from the sample).
2. Variance used **sample formula** (divide by n−1) rather than
   population formula (divide by n).
3. Annualized with **sqrt(365)** (crypto calendar) rather than
   **sqrt(252)** (trading days, equity convention).

Starting with this report, Sharpe daily uses the standard convention
for quant reporting and matches the internal backtest:

1. Daily P&L series includes **every day in the measurement window**,
   with zeros on days without trades.
2. Variance uses **population formula** (divide by n).
3. Annualization factor is **sqrt(252)**.

### Why this matters

The old convention inflated Sharpe daily by two compounding effects:
ignoring zero days reduced the denominator (less variance), and
sqrt(365) rather than sqrt(252) scaled the result up by ~17%. Both
pushed the number upward relative to a fair comparison with the
research backtest's own Sharpe numbers.

### Quantification for 2026-W16

With the methodology change applied to the same trade data:

- **Combined Sharpe daily**: +5.69 → **+4.81** (−15.5%)
- **Daily horizon**: +6.51 → **+5.52** (−15.2%)
- **Weekly horizon**: previously "insufficient days" → **+9.25**
- **Monthly horizon**: previously "insufficient days" → **−6.51**

Weekly and monthly now produce a Sharpe figure because the zero-day
inclusion means the 5-day minimum sample threshold is met (the
window contains 7 full days). Monthly is negative because the four
closed trades in the window are all losers, and the new methodology
surfaces this honestly rather than reporting "insufficient".

### Exit scenario expansion

The same section that displays P&L under mark-exit and ask-exit
(disclosed in the first part of this session) now also displays
Sharpe daily under the two scenarios, side by side. The methodology
described here applies identically to both — only the P&L series
differs.

### No retroactive modification

All prior weekly reports stand with the numbers they showed. They
were computed correctly under the convention in force at that time.
The underlying trade data in `events.jsonl` is unchanged and can be
used to reconstruct Sharpe under any chosen convention.

---

## 2026-04-21 (session 59): PT/BT parity policy revision and operational override

### What changed — in plain language

Prior sessions (48 in particular) established a principle of
strict parity between the backtest (BT) that produced our
published track record and the paper trading engine (PT) running
in real time. Every selection rule was shared through a single
configuration; operational mechanics (cadence, reentry) were the
only documented divergences.

This session revised that principle. Going forward, the PT may
deliberately diverge from the BT in operational parameters when:

1. Direct evidence from the live PT run shows the canonical BT
   parameter is dominated in the current regime.
2. Cross-regime analysis (holdout bear + held-out bull) confirms
   the dominance is not an artifact of a single sample.
3. The divergence is applied via an explicit, named override —
   not by editing the shared configuration — so the published
   BT numbers, which investors can reproduce, are preserved.

The BT numbers in our track record are the number investors
should reproduce. The PT numbers in our public reports are the
numbers that reflect what the live operation actually did. When
those two diverge by design (as they do starting with this
session), both remain faithful to their own convention.

### First deliberate divergence — near-expiry entry/exit handling

The BT applies a near-expiry cutoff (both as a gate that rejects
new entries when the contract is close to expiration AND as a
forced-exit trigger when an open contract is in-the-money near
expiration). This cutoff exists to protect against paths where
a contract that crosses the strike remains in-the-money through
settlement.

**Finding:** a cross-regime sweep conducted this session showed
the canonical cutoff is dominated in the current market regime:

- For two of the three horizons, the BT is mathematically
  indifferent to the cutoff across the backtest range tested
  (the cutoff never activates on the BT cadence of one
  observation per day per contract).
- On the third horizon, a looser cutoff dominates the canonical
  value in the held-out bear sample on every individual axis
  (daily Sharpe, annualized ROI, max drawdown, profit factor).
- On the PT live cadence (continuous), the canonical cutoff
  activates materially because the PT observes intra-day state
  the BT does not. Across the 8 days of live run accumulated
  before this session, the cutoff forced approximately 13%
  of the exits to-date on terms that, under natural expiration,
  would have produced better outcomes in the realized market
  path.

**Back-tested impact on the live sample (counterfactual, same
trade data, re-evaluated under the looser cutoff):**

- Combined P&L: +0.060 BTC → +0.187 BTC (~3.1×)
- Combined daily Sharpe: +2.78 → +9.02
- Combined Calmar: +32.8 → +152.8
- Combined peak IM / AUM: unchanged

**Caveat — regime.** A separate held-out bull sample (Q4-2024
freeze) showed that on one of the three horizons, a *tighter*
cutoff than the canonical value is dominant in strong-bull
conditions. The current live run is in a bear/sideways regime
and a strong-bull episode is not represented in the live PT
sample. The override adopted here is correct for the current
regime and may become sub-optimal if a sustained bull regime
develops. A regime-detecting switch (automated reactivation of
the BT-canonical cutoff under bull) is on the internal backlog.

### Override applied

A named override — scoped to the PT engine, not to the shared
BT/PT configuration — replaces the near-expiry cutoff for all
three horizons. The override is explicit in code, documented
inline, and passed to the real-time scoring layer as an optional
parameter that defaults to `None` (BT-canonical behavior).
Numerical values of the override are part of the proprietary
ruleset and are not disclosed here.

### What remains shared between BT and PT

All selection parameters previously established (moneyness
range, maturity range, deviation threshold, top-K per time
bucket per day, alpha-exit ratio, minimum bid filter) continue
to be sourced from a single configuration object imported by
both the BT and the PT. Universe classification continues to
use `settlement_period` as established in session 48. The only
operational parameter deliberately diverging, as of this
session, is the near-expiry cutoff described above.

### What the PT reports show starting this session

- The existing "PT vs BT benchmark" table in the weekly report
  is unchanged.
- A new "Calmar / MDD comparison" table is added, showing BT
  canonical Calmar, PT Calmar under both the optimistic (mark)
  and pessimistic (ask) exit conventions from session 55, and
  the delta PT-mark minus BT-canonical. Calmar is descriptive
  (same status as the ROI deviation table since session 55) and
  does not trigger an automatic alert.

### No retroactive modification

All prior weekly reports stand. The underlying trade data in
`events.jsonl` is unchanged. Trades opened before the override
was applied remain as they were executed; the override affects
only decisions taken after its deployment.

---

## 2026-04-21 (session 60): second deliberate divergence — daily entry time-to-expiry filter

### Summary of what changed

Following the principle established in session 59 — that PT may
diverge from BT on operational parameters when cross-scenario
evidence justifies — a second override has been added:

- A daily-horizon cap on time-to-expiry at entry has been tightened
  in the PT operational path, without changing the BT canonical
  values.
- The BT canonical parameters remain exactly as reported in
  every prior weekly/monthly report.

This is the second and only other operational parameter
deliberately diverging.

### Motivation — in plain language

A post-mortem of the worst paper-trading losses since go-live
identified a specific pattern: a disproportionate share of the
deepest losses came from contracts entered in a narrow operational
window — newly listed contracts very close to their initial
moment of creation, when the order book is still forming and
trading conditions are less favorable than at other times of day.

The backtest does not sample that window (it uses a single
trade per day from the middle of the trading window), so the
pattern is invisible retrospectively. The PT, which evaluates
every minute, picks up the cluster.

### What remains shared between BT and PT

- The canonical universe definition (contracts segregated by
  settlement period).
- The selection rules (threshold, top-K per bucket, alpha-exit,
  moneyness bounds, and the general time-to-expiry window at
  the BT-canonical width).
- The margin/AUM convention, ROI formula, Sharpe/Sortino/Calmar
  methodology, and disclosure framework.

### Override applied

- Scope: daily horizon only.
- Monthly and weekly: canonical time-to-expiry filter preserved.
  Paper-trading sample for those horizons is too small to draw
  operational conclusions yet; they will be reassessed after
  approximately 60 days of PT data.
- Mechanism: the override tightens the upper bound of the entry
  window while preserving the lower bound (expiry-guard already
  at zero from session 59). Exact numerical value is preserved
  as proprietary ruleset.

### What the PT reports show

All metrics and tables (Sharpe mark/ask, Sortino, Calmar, ROI vs
BT pro-rata, execution scenarios) continue to be produced with
the same methodology established in sessions 55 and 59. The
only change is a gradual reduction in number of daily entries
per day — consistent with rejecting the cluster identified.

### No retroactive modification

All prior weekly reports stand. The underlying trade data in
`events.jsonl` is unchanged. Trades opened before this override
was applied remain as they were executed; the override affects
only decisions taken after its deployment.

---

## 2026-04-22 (session 61): third deliberate divergence — daily intra-cycle ranking

### Background

Session 61 analyzed which features of an elegible contract best
predict realized PnL, both in the backtest universe and in the
live paper-trading clean subset. Two approaches were applied
(Spearman IC with bootstrap 95% CI N=500, and Mann-Whitney
top-quartile vs baseline with Cliff's delta) across 12 candidate
features, split by exit reason to separate real signal from
mathematical tautology.

The canonical intra-cycle ranking used by both the backtest and
the paper trader is proprietary. It selects the top-K candidates
per time bucket per cycle using one particular quality score
derived from the TK model. This disclosure is about the change
from that score to a different quality criterion, applied only
to the daily horizon.

### What the analysis found, in plain language

Within the pool of contracts that already passed the entry filter
(i.e. contracts the model has classified as overpriced relative
to its fair-price estimate), the proprietary quality score used
for ranking has **no statistically significant correlation with
realized PnL**: Spearman ρ ≈ 0 across all exit-reason strata in
both backtest and paper-trading samples. Confirms earlier findings
(sessions 16-17, IC of the TK ranking is effectively zero within
the already-filtered pool).

A non-tautological alternative feature — moneyness (spot/strike)
— has strong positive correlation with PnL across both samples
and both regimes:

- Backtest daily alpha-exit stratum (n=299): ρ = +0.75
- Backtest daily expired-OTM stratum (n=458): ρ = +0.49
- Paper-trading daily alpha-exit stratum (n=61): ρ = +0.57

Direction and magnitude consistent across environments. Mechanism:
in a short-call bear regime where 94% of entries expire out-of-
the-money, PnL_net is roughly proportional to the gross premium
captured. Near-ATM contracts have gross premium 2-3× higher than
deep-OTM contracts at the same level of relative overpricing.

### Counterfactual

- Backtest daily, same canonical ruleset replacing ranking score
  with moneyness-desc as the tiebreaker within each time bucket:
  - Bear holdout: ROI/year improves, Sortino improves, Calmar
    improves, Sharpe roughly unchanged. MDD absolute slightly
    worse (near-ATM carries more gamma risk), but as a fraction
    of the equity peak is unchanged.
  - Q4-2024 bull freeze (out-of-sample): ROI/year, Sortino,
    Calmar, and Sharpe all improve materially. Cross-regime
    validated in the only bull OOS sample available.
- Paper-trading historical counterfactual: of 88 cycles with a
  committed entry, 64 (73%) would have selected at least one
  different instrument under moneyness-desc ranking. Systematic
  pattern: the proprietary score tends to pick deeper-OTM strikes
  (where a small absolute discrepancy from fair price shows up as
  a large percentage score but the gross premium is small);
  moneyness-desc picks near-ATM strikes with much larger gross
  premium. The daily horizon hits n_eligible > 3 within a single
  cycle in 94% of cycles, so the ranking criterion changes the
  operational selection in nearly every committed cycle.

### Rationale for the override

The proprietary score responds to the question *"which contract
is most overpriced relative to fair value?"* — an excellent
question for defining the *universe* of eligible short-call
trades. The empirical finding of session 61 is that this same
score is essentially uninformative for the *within-pool ranking*
question *"which of these will realize the most PnL?"*. The
moneyness criterion answers the latter directly in a bear-dominant
regime. The universe filter (the 12% overpricing threshold)
remains unchanged. The exit rule (alpha-exit at α=90%) remains
unchanged. Only the tiebreaker among already-elegible candidates
is revised.

### Override applied

- Scope: daily horizon only.
- Monthly: trade-off — more absolute PnL but a lower Sharpe (−0.99
  in bear); daily-like dominance does not hold. Not applied.
- Weekly: dominated by the canonical ranking in the bear holdout
  sample; dominates only in the Q4-2024 bull sample. Not applied
  until a regime-detector can condition it.
- Mechanism: the tiebreaker within each time bucket per cycle
  is moneyness-desc instead of the canonical proprietary score.
  All other filters (universe, capacity cap, reentry threshold,
  expiry-guard override, time-to-expiry override, minimum bid)
  remain as previously disclosed.

### What the PT reports show

All metrics and tables produced since session 61 reflect this
override for the daily horizon. The override affects which
contracts enter the book, not how any entered contract is
priced, monitored, or closed. Reports from prior weekly cycles
are unchanged.

### No retroactive modification

All prior weekly reports stand. The underlying trade data in
`events.jsonl` is unchanged. Trades opened before this override
was applied remain as they were executed; the override affects
only decisions taken after its deployment.

---

## 2026-04-23 (session 63): Break-even filter — canonicalization across BT and PT

### What changed — in plain language

The minimum-premium filter documented in the session 50 entry
above (April 16 in this log) was, until this session, a rule
local to the paper trader only. The backtest that generates the
published track record did not apply the same filter, so a small
number of trades with premium below the economic break-even were
included in the backtest history even though they would have
been rejected by the live paper trader.

The principle matters more than the magnitude: **a trade whose
maximum gross P&L under the exit rule is below the fixed
execution costs is guaranteed to lose money on entry**. That is
not a regime-dependent heuristic; it is arithmetic. The filter
therefore belongs to both phases of testing (backtest and paper
trading), uniformly across all three horizons, and is now sourced
from a single shared configuration.

### What this session did

1. Formalized the threshold as a derived value rather than a
   hard-coded number. The derivation is a function of the fixed
   per-leg exchange fee, the α capture rate of the exit rule,
   the expected bid-ask half-spread (as a fraction of premium),
   and a small safety margin over the theoretical break-even.
   The helper lives in `backtest_costs.compute_y_entry_min_btc()`
   (research repo).
2. The threshold is wired into `HORIZON_STRATEGY_FILTERS` for
   monthly, weekly, and daily horizons — the same single source
   of truth introduced in session 48 for universe parity.
3. The paper trader now reads the threshold from the same dict
   instead of carrying its own constant. An assertion at import
   time verifies that all three horizon thresholds match (they
   are uniform by design; if they diverge in the future, the
   paper trader's filter logic would need to become
   horizon-aware).
4. The derived threshold, under conservative defaults (fee, α,
   L2, safety), is slightly more restrictive than the legacy
   value (session 50, ~14% above). The legacy value ignored
   the L2 term in the break-even; the new derivation includes
   it explicitly.

### Quantification on the published track record

The filter is re-applied to the backtest holdout and recalibrates
the reference numbers. **Only the monthly horizon is affected
materially**:

- Monthly (bear holdout, pre- → post-canonicalization): ~33
  trades filtered out of ~209 in the sample (~15%). Net ROI
  rises from +13.2% → **+14.8%** (+1.6pp); Sharpe_d rises
  +5.46 → +5.56. Win rate rises 95% → 99% (the removed trades
  were consistently small net losses). AUM drops ~7% because
  peak simultaneous initial margin is lower.
- Weekly (bear holdout): **no trades affected.** Weekly has a
  tighter moneyness ceiling which already excluded the premium
  range where the filter binds.
- Daily (bear holdout): **no trades affected.** Short time-to-
  expiry keeps premiums above the threshold even for deeper-OTM
  strikes.
- Q4-2024 bull freeze (all horizons): **no trades affected.**
  Bull regimes have higher premiums on average.

The paper trading log is unchanged — the filter has been active
on the paper trader since session 50, so every trade in
`events.jsonl` is already filtered. The 2 trades disclosed in
the session 50 entry (which would also have been rejected under
the new, stricter threshold) remain as recorded; they are
pre-fix artifacts from 2026-04-13 to 2026-04-16.

### What changes in the published performance table

Starting with the next weekly/monthly report, the monthly horizon
numbers use the recalibrated reference. Other horizons are
unchanged. The ROI gap between the paper trader and the backtest
should narrow slightly on the monthly side because the backtest
is no longer inflated by the loss-certain tail the paper trader
was already rejecting.

### Why now

Diagnostic work in this session confirmed that four of the seven
closed monthly positions in the paper trader (session 62 status
report) were entered before the session 50 fix and would have
been blocked under the now-canonical threshold. The remaining
three were cross-universe from before the session 48 fix. The
monthly horizon stopping-rule trigger visible in those reports
is an artifact of those two pre-fix regimes, not degradation of
the strategy; the canonicalization in this session ensures both
phases reject the same loss-certain tail going forward.

### How to verify

- In the research repo, the helper is in
  `src/backtest_costs.py::compute_y_entry_min_btc` with full
  docstring and derivation.
- In this repo, `events.jsonl` has always carried `best_bid` at
  entry. Any third party can compute the break-even threshold
  from the published Deribit fee schedule and the α of the exit
  rule (documented in `README.md`) and verify that no entry
  event from 2026-04-16 onward has `exec_btc` below that
  threshold.

### Audit trail

- Research repo backlog item: B224 (internal reference).
- Tests: 8 new unit tests in `tests/test_backtest_costs.py` and
  `tests/test_paper_trading_cycle.py` covering the helper,
  horizon uniformity, and the wiring to both phases.
- Suite: 613 tests passing as of this session.
