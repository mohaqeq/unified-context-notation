# Retry many failed webhook deliveries at once

After an outage on a receiving system, operators end up with hundreds of `FAILED` event deliveries and today they have to call `eventDeliveryRetry` once for each of them. Please add a mutation `eventDeliveryBulkRetry(ids: [ID!]!)` that retries all the given event deliveries in one call. It needs the same permission as `eventDeliveryRetry` (`MANAGE_APPS`) and returns `count` (the number of deliveries scheduled for another attempt) and the usual `errors` list (`WebhookError`). For every delivery the effect must be the same as for `eventDeliveryRetry`: its status goes back to `PENDING` and a new attempt to send it is scheduled on the existing send task (`send_webhook_request_async`, called with the delivery's id as `event_delivery_id`).

If any of the IDs does not resolve to an event delivery (wrong type, unknown, or belonging to a removed app), return a single error on the `ids` field and change nothing.
