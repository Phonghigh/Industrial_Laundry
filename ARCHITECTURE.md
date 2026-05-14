# Industrial Laundry — Operational Event Capture System

## Project Philosophy

> "Software must blend into workflow. Workers don't adapt to software — software adapts to workers."

This is **not** an ERP dashboard. It is a **low-friction operational event capture system** for an industrial laundry facility. Every architectural decision must reduce operational friction. If it adds a step for the worker, it's wrong.

**North star metric:** Worker interaction time < 2 seconds per event.

---

## Domain Context

**Setting:** Industrial laundry facility (Phú Quốc deployment). ~50–200 workers. Multiple processing stations. High noise, wet hands, low digital literacy.

**Core constraint:** Workers cannot change their workflow. The system instruments what already happens.

**Station flow:**
```
Intake → Sorting → Washing → Drying → Ironing → Packing → Dispatch
```

Each batch of laundry moves through stations. Each station transition = 1 operational event to capture.

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend API | FastAPI (Python 3.12) | Async, fast, clean OpenAPI |
| Event Bus | Redis Streams | Buffering, replay, async decoupling |
| Database | PostgreSQL 16 | Append-only events, JSONB metadata |
| Station App | PWA (React + Vite) | No app install, offline-first via IndexedDB |
| Dashboard | React + Vite | Real-time via SSE |
| Observability | Grafana + Loki + Prometheus | Operational visibility is product-critical |
| Container | Docker Compose | Single-command factory deployment |

---

## Architecture Principles

### 1. Event-Driven, Append-Only

Never update state directly. Always append an event.

```json
{
  "batch_id": "BATCH_2041",
  "station_id": "drying",
  "event_type": "completed",
  "device_id": "station-device-3",
  "idempotency_key": "uuid-v4",
  "timestamp": "2026-05-10T13:22:11Z",
  "metadata": {}
}
```

**Why:** Traceability, replayability, debugging, analytics. An event log is an operational audit trail.

### 2. Offline-First on Station Devices

Assume Wi-Fi is unreliable. Station app must:
- Save events to IndexedDB **immediately** on worker action
- Confirm to worker **immediately** (optimistic UI)
- Sync to backend in background with retry + backoff
- Use idempotency keys to prevent duplicates on retry

### 3. Graceful Degradation

| Failure | Behaviour |
|---------|-----------|
| Wi-Fi lost | Queue locally, sync when restored |
| ASR low confidence | Ask re-confirm or fall back to button |
| Device reboot | Recover event log from IndexedDB |
| Redis down | API persists direct to PostgreSQL with retry |
| Dashboard down | Stations fully operational, zero impact |

### 4. Multi-Tenant Ready

All tables have `tenant_id`. One deployment can serve multiple factories. Schema:
```
Tenant → Factory → Stations → Devices → Workers
```

---

## Project Structure

```
Industrial_Laundry/
├── ARCHITECTURE.md                  # Architecture and dev guidelines
├── docs/
│   ├── event-schema.md              # All event types & payloads
│   ├── failure-modes.md             # Failure analysis
│   ├── conventions.md               # Naming and coding conventions
│   ├── patterns.md                  # Canonical code patterns
│   └── workflows.md                 # Dev workflows
├── backend/                         # FastAPI service
│   ├── app/
│   │   ├── main.py                  # App factory
│   │   ├── core/
│   │   │   ├── config.py            # Settings via pydantic-settings
│   │   │   ├── database.py          # Async SQLAlchemy engine
│   │   │   └── redis.py             # Redis client + stream helpers
│   │   ├── api/v1/
│   │   │   ├── router.py            # Route aggregator
│   │   │   └── endpoints/
│   │   │       ├── events.py        # POST /events (ingest)
│   │   │       ├── batches.py       # GET/POST /batches
│   │   │       ├── stations.py      # GET /stations
│   │   │       ├── alerts.py        # GET /alerts
│   │   │       └── manager.py       # GET /manager/overview (SSE)
│   │   ├── models/                  # SQLAlchemy ORM models
│   │   │   ├── base.py
│   │   │   ├── batch.py
│   │   │   ├── event.py
│   │   │   └── station.py
│   │   ├── schemas/                 # Pydantic request/response schemas
│   │   │   ├── event.py
│   │   │   ├── batch.py
│   │   │   └── station.py
│   │   ├── services/
│   │   │   ├── event_processor.py   # Business logic for events
│   │   │   ├── batch_lifecycle.py   # Batch status transitions
│   │   │   └── alert_engine.py      # Stuck batch / inactivity detection
│   │   ├── workers/
│   │   │   ├── stream_consumer.py   # Redis Streams consumer
│   │   │   └── consumer_main.py     # Worker service entrypoint
│   │   └── middleware/
│   │       ├── tenant.py            # Tenant extraction
│   │       └── observability.py     # Prometheus instrumentation
│   ├── tests/
│   │   ├── unit/
│   │   └── integration/
│   ├── alembic/                     # DB migrations
│   ├── pyproject.toml
│   └── Dockerfile
├── station-app/                     # PWA for station tablets
│   ├── src/
│   │   ├── components/              # BigButton, QRScanner, StatusBanner
│   │   ├── services/
│   │   │   ├── localQueue.ts        # IndexedDB event queue
│   │   │   ├── syncEngine.ts        # Background sync + retry
│   │   │   ├── deviceConfig.ts      # Station ID validation
│   │   │   └── voiceAssist.ts       # ASR (augmentation only, never required)
│   │   ├── stores/                  # Zustand state
│   │   └── types/
│   ├── public/
│   ├── package.json
│   └── Dockerfile
├── dashboard/                       # Manager real-time dashboard
│   ├── src/
│   │   ├── components/              # BottleneckPanel, StuckBatchAlert, ThroughputMeter
│   │   ├── services/
│   │   │   └── sseClient.ts         # SSE connection
│   │   ├── stores/
│   │   └── types/
│   ├── package.json
│   └── Dockerfile
├── infra/
│   ├── docker-compose.yml           # Production stack
│   ├── docker-compose.dev.yml       # Dev overrides
│   ├── docker-compose.infra.yml     # Infrastructure only
│   ├── grafana/
│   ├── prometheus/
│   ├── nginx/
│   └── promtail/
└── scripts/
    ├── seed.py                      # Dev data seeder
    ├── migrate.sh                   # DB migration runner
    └── demo.ps1                     # End-to-end demo
```

---

## Key API Contracts

### POST /api/v1/events
Ingest an operational event from a station device.

```json
// Request
{
  "batch_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "station_id": "3fa85f64-5717-4562-b3fc-2c963f66afa7",
  "event_type": "completed",
  "device_id": "device_android_003",
  "idempotency_key": "3fa85f64-5717-4562-b3fc-2c963f66afa8",
  "timestamp": "2026-05-10T13:22:11Z",
  "metadata": {
    "asr_confidence": 0.94
  }
}

// Response 202 Accepted
{ "event_id": "evt_xxx", "queued": true }
```

### GET /api/v1/manager/overview (SSE)
Server-Sent Events stream for dashboard.

```json
{
  "type": "operational_state",
  "bottlenecks": [{ "station": "drying", "queue_depth": 12, "avg_wait_mins": 38 }],
  "stuck_batches": [{ "batch_id": "BATCH_2041", "station": "ironing", "stuck_mins": 42 }],
  "station_throughput": [{ "station": "sorting", "batches_per_hour": 320 }],
  "inactive_stations": [{ "station_id": "station_5", "silent_mins": 17 }]
}
```

---

## Database Schema (Core)

```sql
CREATE TABLE batches (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     UUID NOT NULL,
  batch_code    VARCHAR(50) UNIQUE NOT NULL,
  customer_id   UUID,
  status        VARCHAR(20) DEFAULT 'in_progress',
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE stations (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id      UUID NOT NULL,
  name           VARCHAR(100) NOT NULL,
  sequence_order INT NOT NULL
);

CREATE TABLE operational_events (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id        UUID NOT NULL,
  batch_id         UUID REFERENCES batches(id),
  station_id       UUID REFERENCES stations(id),
  event_type       VARCHAR(30) NOT NULL,
  device_id        VARCHAR(100),
  idempotency_key  UUID UNIQUE NOT NULL,
  ts               TIMESTAMPTZ NOT NULL,
  sync_status      VARCHAR(20) DEFAULT 'synced',
  metadata         JSONB DEFAULT '{}'
);

CREATE INDEX idx_events_batch_ts   ON operational_events(batch_id, ts DESC);
CREATE INDEX idx_events_station_ts ON operational_events(station_id, ts DESC);
CREATE INDEX idx_events_tenant     ON operational_events(tenant_id);
```

---

## Development Commands

```bash
# Start full stack
docker compose -f infra/docker-compose.yml -f infra/docker-compose.dev.yml up -d

# Backend only (hot reload)
cd backend && uvicorn app.main:app --reload --port 8000

# Station app (dev)
cd station-app && npm run dev

# Dashboard (dev)
cd dashboard && npm run dev

# Run tests
cd backend && pytest tests/ -v

# Run DB migrations
bash scripts/migrate.sh

# Seed dev data
cd backend && python scripts/seed.py
```

---

## Reference Docs

| File | Read when |
|------|-----------|
| [`docs/conventions.md`](docs/conventions.md) | Before writing any new file |
| [`docs/patterns.md`](docs/patterns.md) | Before scaffolding any new endpoint, model, or component |
| [`docs/workflows.md`](docs/workflows.md) | Before running dev commands |
| [`docs/event-schema.md`](docs/event-schema.md) | Before touching event types |
| [`docs/failure-modes.md`](docs/failure-modes.md) | Before changing error handling or degradation behaviour |

---

## Development Guidelines

### Backend

- Use `async`/`await` throughout — no synchronous DB calls ever
- All events go through Redis Streams first, PostgreSQL second
- Every event POST returns `202 Accepted` — not `201`
- Every DB query includes `tenant_id` filter — no exceptions
- Use `structlog` for structured logging — not `print`, not `logging`
- Catch only exceptions you can handle; let others propagate

### Station App

- **IndexedDB first, always.** `enqueue()` runs before any `fetch()` — no exceptions
- Worker sees confirmation **before** network response — optimistic UI
- No blocking spinners — loading state must be non-blocking
- All interactive elements ≥ 64px height — wet hands, gloves
- Station app has one screen: no routing, no menus, no navigation

### Dashboard

- SSE, not WebSocket — dashboard is read-only
- Each SSE event is a full snapshot — replace state, don't merge
- Show operational state in plain language — not raw counts
- Alerts (stuck batch, inactive station) are primary; charts are secondary

### Architecture decisions

1. Read existing docs before changing how something fundamentally works
2. Reliability > Features — every time
3. Offline capability is non-negotiable — no feature may degrade station function
4. Voice is augmentation only — never make it required
5. Document architecture decisions in `docs/` before implementing

### Do NOT

- Build a general-purpose ERP or inventory system
- Add authentication to station devices
- Use ORM lazy loading — always explicit `joinedload` or separate queries
- Add animations or transitions to station app — latency perception matters
- Make any feature that requires a worker to navigate a menu
- Write to `operational_events` with UPDATE or DELETE — insert only
- Omit `tenant_id` from any database query — it is always required
- Use `print()` or Python's `logging` — use `structlog`
- Return raw SQLAlchemy objects from endpoints — always use Pydantic schemas

---

## Observability Targets

| Metric | Alert Threshold |
|--------|----------------|
| `event_ingestion_latency_ms` | p99 > 200ms |
| `sync_failure_rate` | > 2% |
| `station_inactivity_seconds` | > 900s (15min) |
| `device_offline_count` | > 0 (any device) |
| `asr_confidence_score` | avg < 0.85 |
| `redis_stream_backlog` | > 500 events |
| `stuck_batch_count` | > 5 batches |

---

## Failure Mode Reference

| Failure | Immediate Behaviour | Recovery |
|---------|--------------------|----|
| Wi-Fi lost | Save to IndexedDB, confirm to worker | Auto-sync on reconnect |
| ASR < 0.75 confidence | Re-prompt or fall back to button | Worker taps button |
| Device reboot | Reload from IndexedDB on startup | Resume queue sync |
| Redis down | API writes direct to PostgreSQL | Redis consumer catches up on restart |
| PostgreSQL slow | Redis buffers, backpressure alert | Horizontal read replica |
| Dashboard crash | Zero impact on stations | Dashboard auto-reconnects SSE |
| Backend deploy | Rolling restart < 5s gap | Station queue absorbs gap |
