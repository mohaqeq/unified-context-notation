# Flag orders that were paid with a gift card

The storefront wants to show a small "Paid with a gift card" note on the order page, and the customer-service team wants the same flag on the order list. Add a non-null boolean field `hasGiftCardPayment` to the `Order` type.

It is `true` when at least one of the order payment transactions (the transactions backing `Order.transactionSummaries`) used a gift card as its payment method, meaning the transaction payment method type is `GIFT_CARD`, and `false` otherwise, including for orders that have no transactions at all. It must be readable by anyone who can read the order itself, and it must not require any extra permission.
