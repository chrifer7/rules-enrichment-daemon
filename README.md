# rules-enrichment-daemon

Daemon de enrichment desacoplado para órdenes de fulfillment. Lee órdenes candidatas desde API externa, evalúa reglas internas, construye payload de enrichment, lo envía al sistema externo y registra trazabilidad con outbox transaccional.

## Visión general

Flujo principal:

1. Poll de órdenes `READY_FOR_ENRICHMENT` desde API externa.
2. Carga/caché de reglas activas desde DB interna.
3. Evaluación de reglas por specifications declarativas.
4. Construcción de payload de enrichment con builder.
5. Submit a API externa con retry + backoff + jitter.
6. Persistencia local de intentos/resultado/idempotencia.
7. Inserción de eventos en `outbox_messages` dentro de la misma transacción.
8. Worker separado publica outbox a sink desacoplado.

## Arquitectura

- `domain`: entidades, value objects, enums, specifications, servicios.
- `application`: casos de uso, DTOs, facades, puertos y mappers.
- `infrastructure`: DB/ORM, repositorios SQLAlchemy, UoW, HTTP adapters, workers.
- `interfaces`: CLI (`run-daemon`, `publish-outbox`, `seed-rules`, etc.) y health API.
- `shared`: logging ECS, errores tipados, Result, clock, id generator.

## Decisiones clave

- **Transactional Outbox**: evita inconsistencias entre estado local y publicación de eventos.
- **ECS logging a stdout**: observabilidad orientada a Elastic/Kibana.
- **Adapter por puerto para WMS externo**: permite swap simulador -> API real sin tocar el núcleo.
- **Idempotencia**: `processed_orders` con hash de enrichment para evitar reprocesos duplicados.

## Logging ECS

Configuración por env:

- `LOG_ECS_ENABLED=true`
- `LOG_TO_STDOUT=true`
- `LOG_TO_FILE=false` (opcional)

Campos relevantes incluidos en logs:

- `event.action`, `event.category`, `event.outcome`
- `daemon.run_id`, `correlation.id`, `order.id`
- `client.code`, `facility.code`, `attempt`, `duration.ms`
- `error.type`, `error.message`

Ejemplo simplificado:

```json
{
  "@timestamp": "2026-03-07T20:10:12.123Z",
  "log.level": "info",
  "message": "Polling cycle finished",
  "service.name": "rules-enrichment-daemon",
  "event.action": "poll_cycle_end",
  "event.category": "process",
  "event.outcome": "success",
  "daemon.run_id": "f9d4...",
  "duration.ms": 421,
  "orders.fetched": 20,
  "orders.success": 20,
  "orders.failed": 0
}
```

## Estructura

```text
rules-enrichment-daemon/
  src/app/
    domain/
    application/
    infrastructure/
    interfaces/
    shared/
  tests/
    unit/
    integration/
    contract/
  migrations/
  Dockerfile
  docker-compose.yml
  pyproject.toml
  README.md
  examples.http
```

## Base de datos

Tablas principales:

- `enrichment_rules`
- `processing_attempts`
- `processed_orders`
- `outbox_messages`
- `daemon_checkpoints`
- `dead_letter_items`
- `rule_audit_entries`

Migraciones:

```bash
alembic upgrade head
```

## Configuración

Copiar `.env.example` a `.env` y ajustar:

- `EXTERNAL_API_BASE_URL` (simulador Manhattan)
- `DATABASE_URL`
- `POLL_INTERVAL_SECONDS`
- `POLL_BATCH_SIZE`
- `MAX_PROCESSING_ATTEMPTS`
- `OUTBOX_PUBLISH_INTERVAL_SECONDS`

## Ejecución local

Instalación:

```bash
pip install -e .[dev]
```

Seed de reglas:

```bash
seed-rules
```

Daemon:

```bash
run-daemon
```

Publicación outbox manual:

```bash
publish-outbox
```

Health API:

```bash
uvicorn app.interfaces.health.api:app --host 0.0.0.0 --port 8080
```

## Docker

Levantar daemon + postgres:

```bash
docker compose up --build
```

## Tests

```bash
pytest -q
```

Cobertura incluida:

- unit: rule evaluation, payload builder
- integration: repository roundtrip
- contract: shape de payload de enrichment

## Integración con simulador

Se espera API externa compatible con:

- `GET /api/v1/orders?status=READY_FOR_ENRICHMENT&updated_since=...`
- `GET /api/v1/orders/{order_id}`
- `POST /api/v1/orders/{order_id}/enrichment`

## Limitaciones actuales

- Publisher outbox usa sink log/webhook simple (no bus de mensajería real).
- `replay-dead-letter` está como placeholder.
- Métricas Prometheus no implementadas (estructura preparada).
- Elastic APM preparado por configuración, sin agente activado por defecto.
