# OpenTimestamps Proofs

This directory contains cryptographic proofs of temporal existence for `events.jsonl`.

Each pair of files represents one timestamp:
- `events-YYYYMMDD-HHMMSS.sha256` — SHA-256 hash of `events.jsonl` at that moment
- `events-YYYYMMDD-HHMMSS.sha256.ots` — OpenTimestamps proof file (Bitcoin-anchored)

## Verification

```bash
# Install opentimestamps-client
pip install opentimestamps-client

# Verify a proof (requires Bitcoin block confirmation, 1-12h after creation)
ots verify timestamps/events-20260416-134502.sha256.ots

# Upgrade a pending proof (fills in Bitcoin block data)
ots upgrade timestamps/events-20260416-134502.sha256.ots

# Check proof info
ots info timestamps/events-20260416-134502.sha256.ots
```

## What this proves

An OpenTimestamps proof anchored in a Bitcoin block proves that the SHA-256 hash
of `events.jsonl` existed **before** that block was mined. This means:

1. The trade log was not fabricated after the fact (anti-backdating)
2. Combined with the append-only nature of `events.jsonl`, gaps in the log
   (cherry-picking) would be detectable between consecutive timestamps
3. Combined with `api_archive/` (available on request), market prices can be
   independently verified against historical data providers (Tardis.dev, Deribit)
