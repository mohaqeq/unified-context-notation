# Show customers when each refund on their order happened

On the storefront order page, customers can see how much of each payment was refunded (`Order.transactionSummaries { refundedAmount }`), but they keep writing to support asking "when was my money sent back, and was it in one piece or several?". Support wants the page to list the individual refunds.

Add a field `refunds` to the `TransactionSummary` type (the items of `Order.transactionSummaries`). It returns a non-null list with one entry per successful refund of that payment transaction (a transaction event of type `REFUND_SUCCESS`), ordered from the oldest to the newest. Each entry exposes the refunded `amount` (a `Money`) and the `createdAt` date and time of the refund. Refund requests and failed refunds must not appear in the list, and a transaction with no successful refund returns an empty list. Like the rest of `transactionSummaries`, it must be readable by whoever can read the order on the storefront.
