# Show the remaining balance when a customer types in a gift card code

Our storefront checkout has a "Check balance" link next to the gift card input. Today a customer has to add the card to the cart before they can see how much is left on it, and many shoppers just give up when they are not sure the card has enough on it. We want to let them look it up first.

Add a public (no authentication required) GraphQL query `giftCardBalance(code: String!): Money`. It returns the current balance (`amount` and `currency`) of the gift card with that code, but only when the card is usable, meaning it is active and has not expired. When there is no usable gift card with that code the query returns `null` (no GraphQL error). It must work for anonymous callers, logged-in customers and staff alike.
