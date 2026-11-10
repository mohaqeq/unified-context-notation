# Let the thumbnail endpoint choose how an odd size is rounded

Our mobile app builds thumbnail URLs from its screen layout, so it often asks the image proxy for sizes that are not among the generated ones, for example `/thumbnail/<instance_id>/700/`, and receives a thumbnail much larger than it needs (700 is served with the 1024 thumbnail), which costs bandwidth on cellular connections. Please add an optional `rounding` query parameter to the thumbnail endpoint (`/thumbnail/<instance_id>/<size>/` and `/thumbnail/<instance_id>/<size>/<format>/`). Accepted values are `nearest` and `up`, case-insensitive; they mean the same as `NEAREST` and `UP` of the GraphQL `sizeRounding` argument. For example `/thumbnail/<instance_id>/700/?rounding=nearest` must redirect to the 512 thumbnail and `?rounding=up` to the 1024 one. A value that is neither should be answered with a 404 like the other invalid inputs of this endpoint.

Links that do not carry the parameter must keep working.
