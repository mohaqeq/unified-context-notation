# Add an `isExpired` flag to gift cards in the dashboard API

The dashboard gift card list shows an "Expired" badge, and today it works that out in the browser by comparing `expiryDate` with the local clock, which gives wrong answers around midnight for staff in other time zones. Please compute it on the server.

Add a non-null `isExpired: Boolean!` field to the `GiftCard` type. It is `true` when the card has an expiry date that is earlier than today's date (UTC), and `false` when the expiry date is today or later, or when the card has no expiry date. It does not depend on whether the card is active or on its balance.
