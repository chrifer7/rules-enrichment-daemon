# rules-enrichment-daemon

`rules-enrichment-daemon` is a background enrichment service for fulfillment orders.
It continuously fetches candidate orders from an external WMS-compatible API, evaluates business rules, sends enrichment payloads back to the external system, and stores processing/audit data locally.

This repository is intended to be shared across multiple teams, so this README is written as the primary onboarding and operations guide.

## What This Service Does

Main responsibilities:

1. Poll orders with status `READY_FOR_ENRICHMENT` from an external API.
2. Load active enrichment rules from its internal database.
3. Evaluate rules against each order (deterministic rule engine).
4. Build enrichment payloads in a consistent contract format.
5. Submit enrichment to external API with retry/backoff.
6. Persist processing attempts, outcomes, idempotency state, and audit records.
7. Write integration events to a transactional outbox for reliable publishing.

## What This Service Does Not Do

1. It is not an order management system.
2. It is not the source of truth for order lifecycle.
3. It does not include a full enterprise message bus outbox publisher yet (current sink is log/webhook based).

## High-Level Flow

1. Poll candidates from external API.
2. Resolve rule set (with cache/TTL).
3. Evaluate rules and compute enrichment result.
4. Submit enrichment to external API.
5. Persist attempt + status + idempotency hash.
6. Insert outbox event in same transaction.
7. Separate publisher process can publish outbox messages.

## Architecture

The codebase follows a layered structure with clear boundaries:

- `domain`: entities, value objects, rule evaluation logic, business invariants.
- `application`: use cases, DTOs, facades, ports.
- `infrastructure`: SQLAlchemy repositories, DB session/UoW, HTTP adapters, workers.
- `interfaces`: CLI entrypoints and health API.
- `shared`: logging, IDs, result/error helpers, clock.

This separation allows replacing infrastructure (for example, simulator API -> real API) with minimal impact on business logic.

## Repository Structure

```text
rules-enrichment-daemon/
  src/app/
    domain/
    application/
    infrastructure/
    interfaces/
    shared/
  migrations/
  tests/
    unit/
    integration/
    contract/
  openshift/
    dev/
    test/
  Dockerfile
  docker-compose.yml
  pyproject.toml
  README.md
```

## Data Model

Core tables:

- `enrichment_rules`
- `processing_attempts`
- `processed_orders`
- `outbox_messages`
- `daemon_checkpoints`
- `dead_letter_items`
- `rule_audit_entries`

## CLI Commands

Installed scripts (from `pyproject.toml`):

- `run-daemon`
- `publish-outbox`
- `seed-rules`
- `replay-dead-letter` (placeholder)
- `health-check`
- `validate-rules`

## External API Contract Expected

The daemon expects an external API compatible with:

- `GET /api/v1/orders?status=READY_FOR_ENRICHMENT&updated_since=...`
- `GET /api/v1/orders/{order_id}`
- `POST /api/v1/orders/{order_id}/enrichment`

`manhattan-simulator` in this workspace implements this contract for local/dev integration.

## Configuration

Copy `.env.example` to `.env` and adjust values.

Most important variables:

- `EXTERNAL_API_BASE_URL`: external system base URL.
- `DATABASE_URL`: PostgreSQL URL.
- `USE_SQLITE` / `SQLITE_DATABASE_URL`: local SQLite mode.
- `POLL_INTERVAL_SECONDS`
- `POLL_BATCH_SIZE`
- `RULE_CACHE_TTL_SECONDS`
- `MAX_PROCESSING_ATTEMPTS`
- `OUTBOX_PUBLISH_INTERVAL_SECONDS`
- `OUTBOX_SINK_MODE` (`log` or `webhook`)

### Logging / Observability

ECS-style logging is supported:

- `LOG_ECS_ENABLED=true`
- `LOG_TO_STDOUT=true`
- `LOG_TO_FILE=false`

Designed for ingestion into Elastic/Kibana.

## Local Development

### 1) Install

```bash
pip install -e .[dev]
```

### 2) Database migrations

```bash
alembic upgrade head
```

### 3) Seed rules

```bash
seed-rules
```

### 4) Run daemon

```bash
run-daemon
```

### 5) Optional: run health API

```bash
uvicorn app.interfaces.health.api:app --host 0.0.0.0 --port 8080
```

## Docker Compose (Local Integration)

Start daemon + postgres:

```bash
docker compose up --build
```

By default, compose config points the daemon to `http://host.docker.internal:8000` for the simulator.

## Testing

Run test suite:

```bash
pytest -q
```

Test scope includes:

- unit tests (rule engine, payload logic)
- integration tests (repository roundtrip)
- contract tests (payload shape)

## OpenShift Deployment Assets

This repository includes OpenShift manifests under:

- `openshift/dev`
- `openshift/test`

Naming convention (lowercase):

- `-is` for ImageStream
- `-bc` for BuildConfig
- `-d` for Deployment

Automation script:

- `openshift/deploy-rules-enrichment-daemon.ps1`

## Troubleshooting Quick Guide

1. Daemon not processing orders:
- check `EXTERNAL_API_BASE_URL`
- verify simulator availability
- inspect daemon logs

2. DB connection errors:
- validate `DATABASE_URL`
- verify postgres pod/service and migrations

3. Migrations failing:
- inspect job logs
- confirm image contains `alembic.ini` and `migrations/`

## Current Limitations

1. Outbox publisher sink is currently log/webhook oriented, not a full enterprise broker integration.
2. `replay-dead-letter` is still a placeholder command.
3. Prometheus metrics are not implemented yet.

## Collaboration Notes

When contributing:

1. Keep domain logic in `domain`/`application`, not in adapters/controllers.
2. Preserve contract compatibility unless a versioned change is agreed.
3. Update tests and this README for behavior changes affecting operations.
