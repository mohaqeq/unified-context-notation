# ADR 003: Codes never change their target

Status: accepted

## Why immutable

Short links get printed on paper and QR codes and pasted into old emails. If a code could be retargeted,
an old printout could start pointing somewhere unexpected, which is also an abuse vector.

## What this rules out

No endpoint updates the target of an existing code. Disabling a link (abuse) is allowed; changing it is not.
