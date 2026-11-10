# Clean up customer accounts that have been dormant for a long time

For data-retention reasons we need to purge customer accounts that nobody uses any more. Add a plain function `delete_dormant_customers(cutoff)` to `saleor/account/tasks.py` (ops will wire it to a schedule later, so no Celery task decorator and no GraphQL API for now). `cutoff` is a timezone-aware `datetime`.

A customer is dormant when all of the following hold: the account is not staff (`is_staff` is false), the customer has never placed an order (no `Order` references them as `user`), and either `last_login` is earlier than `cutoff`, or the customer never logged in (`last_login` is null) and `date_joined` is earlier than `cutoff`. The function deletes every dormant customer and returns the number of customers it deleted as an `int`. Accounts that are not dormant must be left untouched, and calling it when nothing is dormant returns 0.
