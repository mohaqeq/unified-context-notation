# Staff-created gift cards should get the shop's default expiry

The shop has a "gift card expiry" setting (`giftCardSettings`: never expire, or expire after N days/weeks/months/years). It is honored for gift cards bought as products, but cards that staff create with the `giftCardCreate` mutation come out with no expiry unless the staff member types a date, so these cards silently never expire and our finance team has to chase them.

Change `giftCardCreate` so that when the input has no `expiryDate` (omitted or `null`), the new card gets the expiry that follows from the shop's current gift card settings, calculated the same way as for purchased gift cards (the creation date plus the configured period; no expiry when the shop is set to never expire). An `expiryDate` that staff provide explicitly must still be used as given. The `giftCardUpdate` mutation and cards created in bulk are out of scope.
