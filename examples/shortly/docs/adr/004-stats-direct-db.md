# ADR 004: Stats reads Postgres directly (temporary)

Status: accepted, expires 2027-03-31

## Why a deviation

Hit-count queries through the Links component were too slow. Stats reads the link table directly until the
counters move to their own store.
