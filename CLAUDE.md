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
| Dashboard | React + Vite | Real-time via WebSocket/SSE |
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
├── CLAUDE.md                        # ← You are here
├── .claude/settings.json            # Claude Code permissions & hooks
├── docs/
│   ├── architecture.md              # Deep architecture decisions
│   ├── event-schema.md              # All event types & payloads
│   ├── failure-modes.md             # Failure analysis
│   └── api.md                       # API reference
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
│   │   │   └── alert_engine.py      # Stuck batch / inactivity detection
│   │   ├── workers/
│   │   │   └── stream_consumer.py   # Redis Streams consumer
│   │   └── middleware/
│   │       ├── tenant.py            # Tenant extraction
│   │       └── observability.py     # OpenTelemetry instrumentation
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
│   │   │   └── voiceAssist.ts       # ASR (augmentation, not primary)
│   │   ├── hooks/
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
│   │   ├── hooks/
│   │   ├── stores/
│   │   └── types/
│   ├── package.json
│   └── Dockerfile
├── infra/
│   ├── docker-compose.yml           # Production stack
│   ├── docker-compose.dev.yml       # Dev overrides
│   ├── grafana/
│   ├── prometheus/
│   ├── loki/
│   └── nginx/                       # Reverse proxy config
└── scripts/
    ├── seed.py                      # Dev data seeder
    └── migrate.sh                   # DB migration runner
```

---

## Key API Contracts

### POST /api/v1/events
Ingest an operational event from a station device.

```json
// Request
{
  "batch_id": "BATCH_2041",
  "station_id": "station_drying_01",
  "event_type": "completed",          // started | completed | issue_flagged | skipped
  "device_id": "device_android_003",
  "idempotency_key": "uuid-v4",
  "timestamp": "2026-05-10T13:22:11Z",
  "metadata": {
    "asr_confidence": 0.94,           // if voice-triggered
    "issue_code": null
  }
}

// Response 202 Accepted
{ "event_id": "evt_xxx", "queued": true }
```

### GET /api/v1/manager/overview (SSE)
Server-Sent Events stream for dashboard.

```json
// Event: operational_state
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
-- All tables include tenant_id for multi-tenant isolation

CREATE TABLE batches (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     UUID NOT NULL,
  batch_code    VARCHAR(50) UNIQUE NOT NULL,
  customer_id   UUID,
  status        VARCHAR(20) DEFAULT 'in_progress',  -- in_progress | completed | stuck
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
  event_type       VARCHAR(30) NOT NULL,      -- started | completed | issue_flagged
  device_id        VARCHAR(100),
  idempotency_key  UUID UNIQUE NOT NULL,       -- prevent duplicate on retry
  ts               TIMESTAMPTZ NOT NULL,
  sync_status      VARCHAR(20) DEFAULT 'synced',
  metadata         JSONB DEFAULT '{}'
);

CREATE INDEX idx_events_batch_ts ON operational_events(batch_id, ts DESC);
CREATE INDEX idx_events_station_ts ON operational_events(station_id, ts DESC);
CREATE INDEX idx_events_tenant ON operational_events(tenant_id);
```

---

## Development Commands

```bash
# Start full stack
docker compose -f infra/docker-compose.yml up -d

# Backend only (dev)
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

## Claude Code Guidelines

### When writing backend code:
- Use `async`/`await` throughout — no synchronous DB calls
- All events go through Redis Streams first, PostgreSQL second
- Every event POST must validate idempotency_key and return 202 (not 201)
- Include `tenant_id` in every query — never omit it
- Use `structlog` for structured logging, not `print`

### When writing station-app code:
- **Always** save to IndexedDB before any network call
- UI must confirm to worker **before** network response
- No loading spinners that block interaction — optimistic UI only
- Keep bundle size minimal — these are cheap Android tablets

### When writing dashboard code:
- SSE over WebSocket (simpler, good enough for read-only stream)
- Show operational state, not raw data — derive meaning
- Bottleneck and stuck batch alerts are primary, charts are secondary

### When making architecture decisions:
- Reliability > Features
- Worker friction reduction > Technical elegance
- Offline capability is non-negotiable
- Voice is augmentation, not primary input

### Do NOT:
- Build a general-purpose ERP or inventory system
- Add authentication complexity to station devices (shared, always-on)
- Use ORM lazy loading (explicit eager loads only)
- Add animations or transitions to station app (latency perception)
- Make any feature that requires a worker to navigate a menu

---

## Observability Targets

Track these metrics in Prometheus/Grafana:

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
