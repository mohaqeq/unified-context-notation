# Let merchants move a category to a different parent

Merchants reorganise their catalogue all the time, but today the only way to change where a category sits in the tree is to delete it and create it again under the new parent, which loses its products, metadata and URL. Please add an optional `parent: ID` argument to the `categoryUpdate` mutation (the same argument `categoryCreate` already has). When it is given, the category, together with its whole subtree and its products, ends up under the category with that ID; when the argument is omitted the parent is left untouched, exactly as today. Moving a category under itself or under one of its own descendants must be rejected with a validation error on the `parent` field (code `INVALID`) and change nothing.

Other fields in `input` keep working in the same call (for example renaming and moving at once).
