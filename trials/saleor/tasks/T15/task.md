# Expose the per-line quantity limit on the checkout

The storefront needs to cap the quantity selector on the cart page at the maximum the shop allows for a single variant in a checkout. That limit is the shop setting `limitQuantityPerCheckout`, but `Shop.limitQuantityPerCheckout` requires the `MANAGE_SETTINGS` permission, so an anonymous or customer storefront cannot read it. Please add a non-null `lineQuantityLimit: Int!` field to the `Checkout` type that returns the shop's current `limitQuantityPerCheckout` value, readable by anyone who can read the checkout (no extra permission).

The value must follow the shop setting: after the setting is changed, the next query returns the new number.
