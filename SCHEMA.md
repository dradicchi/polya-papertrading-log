# Event schema — `events.jsonl`

This document specifies the exact fields of every event record in `events.jsonl`.

## Conventions

- **File format:** one JSON object per line. Newline-delimited. No trailing newline after the last event is required but accepted. UTF-8.
- **Append-only:** the file is only ever appended. Lines are never edited or deleted. Correction of a past event is done by appending a new event of type `correction` that references the erroneous event's `event_id` — see §3.9.
- **Timestamps:** all timestamps are ISO 8601 UTC with millisecond precision, e.g. `2026-04-13T12:15:02.341Z`.
- **Prices in BTC:** Deribit inverse BTC options are quoted directly in BTC (not USD). All price fields (`best_bid`, `best_ask`, `mark_price`, `exec_btc`, `fee_btc`, `l2_btc`) are in **BTC**. This follows the Deribit API convention and matches the `M_btc` unit in the strategy's backtesting pipeline.
- **Contracts:** `k = 1` for all entries in v1. The pipeline supports `k > 1` in future versions; the schema is already prepared for it.
- **No model data.** Fields such as signal value, fair-price estimate, regression coefficients, regime filter, or Kalman state are **intentionally omitted**. See the `README.md` for rationale.

## 1. Fields common to all events

| Field | Type | Description |
|---|---|---|
| `schema_version` | string | Version of this schema. Current value: `"v1.0"`. |
| `event_id` | string | Deterministic ID: `sha256(type + "|" + instrument + "|" + ts_utc + "|" + horizon)`, hex-encoded, first 16 chars. |
| `ts_utc` | string | ISO 8601 timestamp with millisecond precision, always UTC (`Z` suffix). The moment the script captured the Deribit snapshot and made the decision. |
| `type` | string | See §2 for the list of valid event types. |
| `horizon` | string | `"monthly"` \| `"weekly"` \| `"daily"` |
| `instrument` | string | Deribit instrument name, e.g. `BTC-17APR26-94000-C`. |
| `side` | string | `"short"` in v1. The schema accepts `"long"` in the future. |
| `api_response_hash` | string | `sha256` of the raw Deribit API JSON response used to generate this event. Allows an auditor to request the original response if Polya preserves it (optional). |

## 2. Event types

| Type | Emitted when | Has fields from §3? |
|---|---|---|
| `entry` | A new short position is opened | §3.1 |
| `exit_target_placed` | Immediately after `entry`, records the computed alpha-exit target price | §3.2 |
| `exit` | A position is closed (any reason) | §3.3 |
| `rejected_no_capital` | A candidate signal was valid but the pot did not have free IM | §3.4 |
| `rejected_already_open` | A candidate signal was valid but the same instrument was already held in that horizon | §3.5 |
| `pause` | A horizon is paused due to a stopping-rule trigger | §3.6 |
| `resume` | A paused horizon is manually resumed | §3.7 |
| `api_failure` | The Deribit public API failed at a scheduled checkpoint | §3.8 |
| `correction` | A previous event is corrected due to a known bug; never by editing | §3.9 |

## 3. Type-specific fields

### 3.1. `entry`

| Field | Type | Description |
|---|---|---|
| `expiry_date` | string | ISO date of contract expiration |
| `strike_usd` | number | Strike K in USD |
| `k` | integer | Number of contracts (always `1` in v1) |
| `s_underlying_usd` | number | Deribit index price at the moment of decision |
| `x` | number | Moneyness `S/K` |
| `best_bid` | number | Best bid in BTC (directly from `get_order_book`) |
| `best_bid_amount` | number | Contracts available at best bid |
| `best_ask` | number | Best ask in BTC |
| `best_ask_amount` | number | Contracts available at best ask |
| `mark_price` | number | Mark price in BTC |
| `exec_btc` | number | Execution price used to simulate the fill. Equals `best_bid` (short sells at bid). |
| `fee_btc` | number | L1 cost: Deribit taker fee for the entry leg, in BTC. Computed via `option_fee_btc(exec_btc)`. |
| `l2_btc` | number | L2 cost: half-spread paid at entry, in BTC. Equals `max(0, mark_price - exec_btc)`. |
| `im_btc` | number | Initial margin committed in BTC per contract. Computed via `compute_im_btc(x, 'call') = max(0.10, 1.15 - 1/x)` for short CALL. |

### 3.2. `exit_target_placed`

| Field | Type | Description |
|---|---|---|
| `ref_entry_event_id` | string | `event_id` of the `entry` this target belongs to |
| `target_btc` | number | `ALPHA_EXIT × entry.exec_btc` where `ALPHA_EXIT = 0.10`. This is the price the monitor watches to trigger an alpha-exit. |

### 3.3. `exit`

| Field | Type | Description |
|---|---|---|
| `ref_entry_event_id` | string | `event_id` of the corresponding `entry` |
| `exit_reason` | string | One of: `"alpha_exit"` \| `"expiry_guard"` \| `"expiry"` \| `"stopped_out"` |
| `s_underlying_usd` | number | Index price at the moment of exit (for `expiry`, at settlement) |
| `x_exit` | number | Moneyness at exit |
| `best_bid`, `best_bid_amount`, `best_ask`, `best_ask_amount`, `mark_price` | numbers | Book state at exit. Omitted if `exit_reason=expiry` and the contract expired OTM (no book read needed). |
| `exec_btc` | number | Simulated execution price. Equals `best_ask` for `alpha_exit` / `expiry_guard`. Equals `max(0, 1 - K/S_settlement)` for `expiry`. `0` if `expiry` and OTM. |
| `fee_btc` | number | L1 for exit leg. `0` if `expiry` and `exec_btc = 0`. |
| `l2_btc` | number | L2 for exit leg. Equals `max(0, exec_btc - mark_price)`. `0` if `expiry` natural OTM. |
| `pnl_gross_btc` | number | `entry.exec_btc - exit.exec_btc` |
| `pnl_net_btc` | number | `pnl_gross_btc − (entry.fee_btc + entry.l2_btc + exit.fee_btc + exit.l2_btc)` |
| `holding_days` | number | `(exit.ts_utc − entry.ts_utc)` in decimal days |

### 3.4. `rejected_no_capital`

| Field | Type | Description |
|---|---|---|
| `strike_usd` | number | |
| `s_underlying_usd` | number | |
| `x` | number | |
| `im_required_btc` | number | IM the candidate would need |
| `im_used_btc` | number | IM currently committed across all open positions |
| `im_available_btc` | number | `9.6 - im_used_btc` |

### 3.5. `rejected_already_open`

| Field | Type | Description |
|---|---|---|
| `ref_open_event_id` | string | `event_id` of the pre-existing `entry` for the same `(instrument, horizon)` |

### 3.6. `pause`

| Field | Type | Description |
|---|---|---|
| `trigger` | string | `"mdd_5x"` \| `"rmse_1.5x_14d"` \| `"wr_30d_below_60"` \| `"manual"` |
| `trigger_detail` | string | Human-readable details of the metric that triggered the pause |
| `horizon_affected` | string | Same as top-level `horizon` but restated for clarity |

### 3.7. `resume`

| Field | Type | Description |
|---|---|---|
| `ref_pause_event_id` | string | `event_id` of the pause event being reversed |
| `reason` | string | Free-text justification for the resume (will appear in the public log) |

### 3.8. `api_failure`

| Field | Type | Description |
|---|---|---|
| `endpoint` | string | Deribit endpoint that failed, e.g. `get_order_book` |
| `attempted_instrument` | string \| null | Instrument we were querying, if applicable |
| `error_message` | string | Short description of the failure mode |

### 3.9. `correction`

| Field | Type | Description |
|---|---|---|
| `ref_target_event_id` | string | `event_id` of the previous event being corrected |
| `reason` | string | Explanation of the bug, referencing a hotfix commit if applicable |
| `fields_corrected` | object | `{"field_name": new_value, ...}` — the corrected values. Old values can be inspected in the original event. |

Corrections **never delete or edit the original event**; they are additional entries that an auditor can follow via `ref_target_event_id`.

## 4. Mathematical identities an auditor can check

For any `(entry, exit)` pair sharing the same `ref_entry_event_id`:

```
exit.pnl_gross_btc == entry.exec_btc - exit.exec_btc
exit.pnl_net_btc   == exit.pnl_gross_btc - (entry.fee_btc + entry.l2_btc + exit.fee_btc + exit.l2_btc)
entry.im_btc        == max(0.10, 1.15 - 1/entry.x)   for side='short' and call options
```

For any single event of type `entry`:

```
entry.fee_btc     == option_fee_btc(entry.exec_btc)
                  == max(0.0001, min(0.0003, 0.125 * entry.exec_btc))

entry.l2_btc      == max(0, entry.mark_price - entry.exec_btc)
entry.exec_btc    == entry.best_bid
```

For any single event of type `exit` where `exit_reason ∈ {alpha_exit, expiry_guard}`:

```
exit.fee_btc      == option_fee_btc(exit.exec_btc)
exit.l2_btc       == max(0, exit.exec_btc - exit.mark_price)
exit.exec_btc     == exit.best_ask
```

For an `exit` where `exit_reason == 'expiry'`:
- If OTM at settlement (`s_underlying_usd < strike_usd` for CALL): `exec_btc == 0`, `fee_btc == 0`, `l2_btc == 0`, `pnl_net_btc == entry.exec_btc - entry.fee_btc - entry.l2_btc` (full premium retained minus entry costs only).
- If ITM at settlement: `exec_btc == max(0, 1 - strike_usd/s_underlying_usd)` in BTC.

All of the above are verifiable from the repo alone. The only external dependency for a full audit is cross-checking the declared `best_bid`/`best_ask`/`mark_price` against the Deribit public API at the declared `ts_utc` — which requires either a live query (for very recent events) or a historical tick archive (e.g. [tardis.dev](https://tardis.dev)) for older events.

## 5. Schema evolution

Any change to the schema bumps `schema_version`. The first version is `v1.0`. Changes that add new optional fields are backwards-compatible (`v1.x`). Changes that remove fields, rename them, or change their semantics are breaking and bump to `v2.0`. Breaking changes are communicated in `CHANGELOG.md` and include a migration guide. Events emitted under a previous schema version are **never retroactively re-encoded** — the `schema_version` field lets the auditor know which rules to apply to each line.
