# Allocation service: instructions for coding agents

This is the example application of "Architecture Patterns with Python". Follow its architecture strictly.

## Architecture (package `allocation`, under `src/`)

- `domain/` (Product aggregate, Batch, OrderLine, commands, events) depends on **nothing** outside the domain:
  no service layer, adapters, entrypoints, frameworks or ORM. This is the most important rule.
- `service_layer/` (handlers, message bus, unit of work) may use the domain, the adapters and `config`.
- `adapters/` (ORM mapping, repository, notifications, Redis publisher) may use the domain and `config`.
- `entrypoints/` (Flask API, Redis consumer) may use the domain (commands), the service layer, `bootstrap`,
  `views` and `config`. Entrypoints never talk to adapters directly: go through commands, the message bus and views.
- `bootstrap.py` wires adapters and the service layer. `views.py` (read side) uses the service layer (unit of work).

## Library rules

- SQLAlchemy only in `adapters/` and `service_layer/unit_of_work.py`.
- Flask only in `entrypoints/`.
- Redis only in `adapters/` and `entrypoints/`.

## Business rules

- Allocate to the batch with available quantity, warehouse stock first, then earliest ETA.
- If no batch has enough quantity, emit `OutOfStock` and allocate nothing.
- Allocating the same order line twice counts once.
- When a batch quantity is reduced below its allocations, deallocate lines and reallocate them.
- When a product is out of stock, email stock@made.com.
