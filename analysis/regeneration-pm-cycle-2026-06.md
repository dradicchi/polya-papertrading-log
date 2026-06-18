# Resilience note — regeneration through the PM-002 / PM-003 cycle

**2026-06-03 → 2026-06-17. Two consecutive adverse events absorbed by the
live daily book, with positive cumulative P&L throughout.**

---

## Summary

Over a 15-day window the live daily short-CALL book faced two adverse moves
in BTC — including a +9% rally (60,900 → 66,400 USD) — and still closed the
period at **+0.322 BTC cumulative** (paper, 1 contract per signal), without
its equity ever falling below the level at which the window opened.

This note records the **regeneration behaviour** that investors have asked
about most often, and — with equal weight — the **condition under which it
holds**. The first half is the result; the second half is what keeps it
honest.

---

## The two events

| Event | Window | BTC trigger | Drawdown | Recovery |
|---|---|---|---|---|
| PM-002 | Jun 6–8 | +3.9% spike that **reversed** | −0.030 BTC | 1 day |
| PM-003 | Jun 12–16 | +9% rally that **persisted** | −0.176 BTC | in progress (36% in 2 days) |

## Resilience metrics

- **Equity never went negative.** The worst point (PM-003 trough, +0.258)
  was roughly 10× the level at which the window opened (+0.025). The
  drawdown was against *accumulated gains*, not against principal — the
  book gave back part of a +0.434 peak, not its capital base.
- **Regeneration outpaced the damage in normal markets.** Between the two
  events (Jun 9–11) the book gained +0.166 in two days — larger than the
  PM-002 drawdown itself.
- **Post-trough regeneration rate:** +0.032 BTC per up-day.
- A more conservative deep-out-of-the-money reference variant showed almost
  no drawdown over the same window, at roughly one quarter of the return.
  The visible regeneration is the *price* of the primary book's return
  profile, not a defect.

## The mechanism, in plain language

The book's defence is not avoiding drawdowns — it is **regenerating between
events**. In a normal market it produces P&L at a roughly constant daily
rate. An adverse move produces a drawdown against accumulated gains; the
ongoing production rebuilds it. Maximum drawdown measures the transient
trough; what matters is **recovery time**, not depth.

## The condition under which this holds

Regeneration depends on **recovery windows between events**. The real
sequence was PM-002 → a recovery window (Jun 9–11) → PM-003: it was that
middle window that let the book absorb both shocks. The mechanism **breaks
when events are consecutive** — a sustained grind higher, where the
per-day velocity of the move stays above the book's break-even for many
days and no recovery window opens.

**Validity, stated plainly:** robust for *sparse* adverse events (the
declining/sideways regime observed here); untested, and likely fragile,
for *consecutive* events (a sustained rally) and for a catastrophic tail
(a fast move large enough not to recover within the holding cycle).

## What this proves — and does not

- It proves that, in the observed regime, the strategy absorbs *successive*
  adverse events while staying P&L-positive, and that the drawdown is
  transient (against gains) with a fast, measurable recovery.
- It does **not** prove resilience in a sustained bull grind, nor against a
  catastrophic (≥15%) move. Both remain under test. No methodology change
  is made on the basis of this window.

Sample is small (two events, 15 days), paper-traded, and PM-003 is still
settling at the time of writing.
