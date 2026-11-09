# ADR 001: Random base62 codes

Status: accepted

## Context

A code identifies a link. Two obvious ways to make one: hash the target URL, or draw a random code.

## Why random

The same URL submitted by two owners must get two codes, because statistics and ownership are per
owner. A hash would collide by design. Random 7-character base62 codes give about 3.5 trillion values,
so collisions are rare and a retry loop handles them.

## Consequences

Codes.generate retries up to five times on a collision and then fails with 503.
