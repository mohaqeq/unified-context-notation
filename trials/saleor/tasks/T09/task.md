# Let staff find gift cards that are about to expire

Support wants to send reminders for gift cards that will expire soon, but the `giftCards` query can only be sorted, not filtered, by expiry. Add a new field `expiresBefore: Date` to `GiftCardFilterInput`.

When it is given, `giftCards(filter: {expiresBefore: ...})` returns only the gift cards whose `expiryDate` is strictly earlier than that date. Gift cards without an expiry date are never returned by this filter. It combines with the other filters (for example `isActive`) the usual way, and when it is omitted or `null` the result is unchanged.
