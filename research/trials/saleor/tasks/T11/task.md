# Look up a webhook by its identifier

Apps register their webhooks with an `identifier` that they choose (it is part of the app's manifest), but they never learn the global IDs Saleor assigns. Today an app that wants to inspect one of its webhooks has to call the `webhook(id:)` query, which needs that global ID. Please add an optional `identifier: String` argument to the `webhook` query as an alternative to `id`, returning the webhook that carries that identifier. `id` becomes optional too, and exactly one of the two must be provided; passing both or neither is an error. When no webhook matches the identifier the field returns `null`.

Existing behaviour of `webhook(id:)` must not change. The new argument should have a schema description and follow the usual conventions for new schema surface.
