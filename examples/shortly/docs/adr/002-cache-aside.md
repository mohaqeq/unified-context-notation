# ADR 002: Cache-aside for resolve

Status: accepted

## Why cache-aside

The p99 target for resolve is 50 ms. A read replica would add operational cost; a Redis cache in front of
Postgres meets the target. Postgres stays the source of truth, and cache entries expire within an hour.
