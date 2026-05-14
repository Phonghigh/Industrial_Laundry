# Industrial Laundry — Operational Event Capture System

> "Software must blend into workflow. Workers don't adapt to software — software adapts to workers."

Low-friction operational event capture for an industrial laundry facility. Event-driven, offline-first, real-time operational visibility for managers — with zero added friction for workers.

**North star metric:** Worker interaction time < 2 seconds per event.

---

## What this system actually does

A laundry facility processes batches of laundry through 7 stations:

```
Intake → Sorting → Washing → Drying → Ironing → Packing → Dispatch
```

**The operational problem:** Managers have no visibility into where any batch is, whether any station is bottlenecked, or whether a batch has been stuck for 45 minutes.

**The wrong solution:** An ERP dashboard where workers tap through menus to log progress.

**The right solution:** Instrument what workers already do. Workers make ~1 physical motion per station transition (scan QR + tap 1 button). That produces an event. That event flows to a manager dashboard showing real-time operational state.

---

## Quick Start

### Prerequisites

- Docker Desktop (or Docker + Docker Compose V2)
- Node 20+ (for station-app / dashboard dev)
- Python 3.12+ (for backend dev)

### Option A — Full stack via Docker (recommended)

```bash
# 1. Start all services
docker compose -f infra/docker-compose.yml -f infra/docker-compose.dev.yml up -d

# 2. Apply DB schema (first time or after model changes)
bash scripts/migrate.sh

# 3. Seed dev data (7 stations + 5 batches)
cd backend && python scripts/seed.py

# 4. Verify the API is up
curl http://localhost:8000/health
# → {"status": "ok"}
```

**Services after startup:**

| Service | URL | Credentials |
|---------|-----|-------------|
| API (dev docs) | http://localhost:8000/docs | — |
| Station PWA | http://localhost:5173 | — |
| Manager Dashboard | http://localhost:5174 | — |
| Grafana | http://localhost:3000 | admin / admin |
| Prometheus | http://localhost:9090 | — |
| PostgreSQL | localhost:5432 | postgres / postgres |
| Redis | localhost:6379 | — |

> **Windows PowerShell tip:** `Start http://localhost:8000/docs`  
> **macOS tip:** `open http://localhost:8000/docs`

### Option B — Backend only (fastest iteration)

```bash
# Terminal 1 — Infrastructure
docker compose -f infra/docker-compose.yml up -d db redis

# Terminal 2 — Backend with hot reload
cd backend
pip install uv && uv pip install --system -e ".[dev]"
uvicorn app.main:app --reload --port 8000

# Terminal 3 — Apply schema + seed
bash scripts/migrate.sh
cd backend && python scripts/seed.py
```

### Option C — Station App (dev)

```bash
cd station-app
npm install
echo "VITE_API_BASE=http://localhost:8000" > .env.local
echo "VITE_STATION_ID=<any-uuid>"         >> .env.local
npm run dev
# → http://localhost:5173
```

### Option D — Manager Dashboard (dev)

```bash
cd dashboard
npm install
echo "VITE_API_BASE=http://localhost:8000" > .env.local
npm run dev
# → http://localhost:5174
```

---

## Architecture

### System map

```
                      ┌──────────────────────────────────────┐
                      │          Manager Dashboard            │
                      │     React PWA, SSE read-only          │
                      │  Shows: stuck batches, bottlenecks,   │
                      │  station throughput, inactivity alerts │
                      └───────────────┬──────────────────────┘
                                      │ SSE (text/event-stream)
                                      │ GET /api/v1/manager/overview
                                      │ Full snapshot every 15s
                                      │
                      ┌───────────────▼──────────────────────┐
                      │           FastAPI Backend             │
                      │   Python 3.12, async/await native    │
                      │                                       │
                      │  POST /api/v1/events ──► Redis XADD  │
                      │  GET  /api/v1/manager/overview ──► SSE│
                      │  GET  /health                         │
                      └────────┬─────────────────────────────┘
                               │
           ┌───────────────────┼──────────────────────┐
           │                   │                      │
           ▼                   ▼                      ▼
┌─────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│   Redis Stream  │  │   PostgreSQL 16  │  │   Observability  │
│ key: operational│  │                  │  │                  │
│ _events         │  │  batches         │  │ Prometheus :9090 │
│                 │  │  stations        │  │ Grafana    :3000 │
│ Consumer group: │  │  operational_    │  │ Loki       :3100 │
│ event_processors│  │  events          │  │                  │
└────────┬────────┘  └──────────────────┘  └──────────────────┘
         │                   ▲
         │ XREADGROUP        │ INSERT
         │ batch=50          │
         ▼                   │
┌──────────────────────────────────────────┐
│         Stream Consumer (worker service) │
│   Isolated Docker service                │
│   Reads Redis, writes PostgreSQL         │
└──────────────────────────────────────────┘

                      ▲ POST /api/v1/events
                      │ (when online; with retry)
                      │
         ┌────────────┴────────────────────────────────┐
         │            Station App (PWA)                 │
         │   React + Vite, runs on cheap Android tablet │
         │   Always-on, no login, QR + big buttons      │
         │                                              │
         │   Write path:  action → IndexedDB → confirm  │
         │   Sync path:   setInterval 3s → POST events  │
         └──────────────────────────────────────────────┘
                    ▲ (mounts at each station)
                    │
          Physical Android tablet
          fixed mount, shared device
```

### Tech stack

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

## How it works — layer by layer

### Station App (PWA)

The station app has one job: capture worker actions with zero friction. It operates in two completely independent loops.

**Interaction loop** (sync, < 100ms):

```
Worker scans QR / taps button
        ↓
buildEvent() — generates UUID idempotency key + device timestamp
        ↓
enqueue(event) — writes to IndexedDB immediately
        ↓
showConfirmation() — worker sees green checkmark
← WORKER IS DONE. Network is never in this path.
```

**Sync loop** (async, background every 3s):

```
getPending() — reads IndexedDB where syncStatus = "pending"
        ↓
for each pending event:
    POST /api/v1/events
    ├── 202 Accepted → markSynced(localId)
    ├── 409 Conflict → markSynced(localId)  [already saved — idempotent]
    └── network error → incrementRetry(localId)  [retry next cycle]
```

IndexedDB is persistent storage — events survive device reboots. On restart, `getPending()` returns all unsynced events and the sync loop picks them up automatically.

**IndexedDB event schema:**

```typescript
interface QueuedEvent {
  localId: string;           // crypto.randomUUID()
  batchId: string;           // scanned from QR
  stationId: string;         // configured per device via env
  eventType: "started" | "completed" | "issue_flagged" | "skipped";
  deviceId: string;          // generated once, stored in localStorage
  idempotencyKey: string;    // UUID v4, generated per event
  timestamp: string;         // ISO 8601, device clock
  metadata: Record<string, unknown>;
  syncStatus: "pending" | "synced" | "failed";
  retryCount: number;
}
```

### Backend API (FastAPI)

#### POST /api/v1/events

```
Station device → POST /api/v1/events
                         ↓
       EventIngest schema validation (Pydantic v2)
                         ↓
       redis XADD "operational_events" {...}   ← < 5ms
       (fallback: direct PostgreSQL write if Redis down)
                         ↓
       Return 202 Accepted { event_id, queued: true }
```

The request handler never writes to PostgreSQL — always async via the consumer. P99 response time < 20ms regardless of DB load. A burst of 200 events from a reconnecting device is processed in < 1s.

#### GET /api/v1/manager/overview (SSE)

```
Dashboard connects → StreamingResponse(media_type="text/event-stream")
        ↓
while True:
    state = await alert_engine.compute_operational_state()
    yield f"data: {json.dumps(state)}\n\n"
    await asyncio.sleep(15)
```

Each frame is a complete operational snapshot — not a diff. Dashboard replaces its state on every message. Reconnect is trivial — no state reconstruction needed.

### Redis Streams Consumer

Runs as an isolated Docker `worker` service. Reads from Redis Streams and writes to PostgreSQL in batches of 50.

```
xreadgroup(group="event_processors", count=50, block=5000ms)
        ↓
for each message:
    build OperationalEvent ORM object
        ↓
await db.commit()       ← single batch commit
        ↓
xack(...)               ← only after commit succeeds
```

`xack` happens after `db.commit()`. If the worker crashes mid-batch, Redis re-delivers those entries on restart (`xautoclaim` handles PEL recovery). PostgreSQL's `UNIQUE` constraint on `idempotency_key` ensures duplicate entries are silently ignored.

### Alert Engine

Purely read-only. Derives operational state from the event log via three queries:

- **Stuck batches** — in-progress batches whose most recent event is > 30 minutes ago
- **Inactive stations** — stations with no activity for > 15 minutes (LEFT JOIN handles stations with no events)
- **Station throughput** — completed events per station in the last hour

### Database Schema

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

CREATE INDEX idx_events_batch_ts    ON operational_events(batch_id, ts DESC);
CREATE INDEX idx_events_station_ts  ON operational_events(station_id, ts DESC);
```

All tables carry `tenant_id` for multi-tenant isolation. Every query filters by `tenant_id` — no exceptions.

---

## Request flows

### Flow A — Worker taps "Complete"

```
1.  Worker scans QR → batchId captured
2.  Worker taps COMPLETE (≥ 64px button)
3.  buildEvent() creates event with UUID idempotency key
4.  enqueue(event) → IndexedDB write
5.  showConfirmation() → green checkmark    ← WORKER DONE (< 2s)

6.  [background] syncEngine picks up pending event
7.  POST /api/v1/events
8.  Pydantic validates payload
9.  redis.xadd("operational_events", {...})
10. 202 Accepted returned
11. markSynced(localId) → IndexedDB updated

12. [worker service] xreadgroup picks up entry
13. OperationalEvent ORM built, db.commit() → PostgreSQL INSERT
14. xack → entry marked processed

15. [alert engine] next SSE cycle (≤ 15s later)
16. 3 SQL queries → new operational snapshot
17. Dashboard receives snapshot, UI updates
```

**Latency to worker:** < 100ms  
**Latency to dashboard:** < 15s  
**Durability:** Event is durable in IndexedDB from step 4

### Flow B — Device offline for 30 minutes then reconnects

```
[OFFLINE]
Worker keeps tapping — every action confirmed immediately via IndexedDB.
syncEngine.runSyncCycle() runs every 3s, all POSTs fail, retryCount increments.

[RECONNECT]
syncEngine: getPending() returns N events (e.g. 47)
47 sequential POSTs → all 202 Accepted → all markSynced()
Duration: ~2–5 seconds

[ORDER]
Events carry device-generated timestamps.
Alert engine queries by ts → correct chronological order preserved.
```

**What the manager sees:** Station goes "silent" after 15 minutes → alert fires. When device reconnects, alert clears and history fills in correctly.

### Flow C — Duplicate event (retry after dropped response)

```
Worker taps Complete → idempotencyKey = "abc-123" written to IndexedDB
POST sent → network drops after server receives, before 202 returned
syncEngine catches error → retries with same idempotencyKey = "abc-123"
API accepts → consumer processes → PostgreSQL INSERT attempted
UNIQUE constraint on idempotency_key → duplicate silently ignored, xack proceeds
```

### Flow D — Manager dashboard connects / reconnects

```
Dashboard loads → EventSource("/api/v1/manager/overview")
Server yields full snapshot every 15s.
Browser onmessage → JSON.parse → replace full state → UI re-renders.

If connection drops:
  EventSource auto-reconnects (browser-native, no code needed)
  Next frame is a full snapshot — no state reconstruction required
  Reconnect backoff: browser-managed (1s → 2s → 4s, capped at 64s)
```

### Flow E — Backend deploy (rolling restart)

```
docker compose restart api
  → SIGTERM → connections closed (gap: ~2–5s)
  → Station devices: POST fails → incrementRetry → retry in 3s → zero worker impact
  → Dashboard: SSE drops → EventSource auto-reconnects
  → Worker service: continues processing Redis stream uninterrupted
```

---

## API reference

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
  "timestamp": "2026-05-14T08:30:00Z",
  "metadata": { "asr_confidence": 0.94 }
}

// Response 202 Accepted
{ "event_id": "evt_...", "queued": true }
```

`event_type` values: `started` | `completed` | `issue_flagged` | `skipped`

### GET /api/v1/manager/overview

SSE stream. Yields one `operational_state` event every 15 seconds.

```json
{
  "type": "operational_state",
  "stuck_batches": [
    { "batch_id": "BATCH_2041", "station": "ironing", "stuck_mins": 42 }
  ],
  "bottlenecks": [
    { "station": "drying", "queue_depth": 12, "avg_wait_mins": 38 }
  ],
  "station_throughput": [
    { "station": "sorting", "batches_per_hour": 320 }
  ],
  "inactive_stations": [
    { "station_id": "station_5", "silent_mins": 17 }
  ],
  "computed_at": "2026-05-14T08:30:00Z"
}
```

### GET /health

```json
{ "status": "ok" }
```

---

## Configuration

### Backend (`.env` in `backend/`)

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/industrial_laundry` | Async PostgreSQL URL |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `REDIS_STREAM_KEY` | `operational_events` | Stream name |
| `REDIS_CONSUMER_GROUP` | `event_processors` | Consumer group name |
| `SSE_PING_INTERVAL` | `15` | Seconds between dashboard snapshots |
| `STUCK_BATCH_THRESHOLD_MINS` | `30` | Minutes before batch flagged stuck |
| `STATION_INACTIVITY_THRESHOLD_MINS` | `15` | Minutes before station flagged inactive |
| `ASR_CONFIDENCE_MIN` | `0.75` | Voice confidence fallback threshold |
| `CORS_ORIGINS` | `*` | Allowed CORS origins |
| `ENVIRONMENT` | `development` | Controls debug mode and `/docs` endpoint |

### Station App (`.env.local` in `station-app/`)

| Variable | Required | Purpose |
|----------|----------|---------|
| `VITE_API_BASE` | yes | Backend URL (e.g. `http://localhost:8000`) |
| `VITE_STATION_ID` | yes | UUID of this station — must be a valid UUID |

---

## Failure modes

| Failure | Behaviour | Recovery |
|---------|-----------|----------|
| Wi-Fi lost | Save to IndexedDB, confirm to worker immediately | Auto-sync on reconnect |
| ASR < 0.75 confidence | Re-prompt or fall back to button tap | Worker taps button |
| Device reboot | Reload unsynced events from IndexedDB on startup | Resume queue sync |
| Redis down | API writes direct to PostgreSQL | Redis consumer catches up on restart |
| Worker service crash | PEL recovered via `xautoclaim` on restart | Duplicates rejected by `idempotency_key` UNIQUE constraint |
| Dashboard crash | Zero impact on stations | Dashboard auto-reconnects SSE |
| Backend deploy | 2–5s gap absorbed by station queue | All events eventually sync |

---

## Observability

Prometheus scrapes `api:8000/metrics` every 15 seconds. Grafana dashboards are pre-provisioned.

| Metric | Alert threshold |
|--------|----------------|
| `laundry_event_ingest_latency_seconds` p99 | > 200ms |
| `laundry_sync_failure_rate` | > 2% |
| `laundry_station_inactivity_seconds` | > 900s |
| `laundry_device_offline_count` | > 0 |
| `laundry_asr_confidence_score` avg | < 0.85 |
| `laundry_redis_stream_backlog` | > 500 events |
| `laundry_stuck_batch_count` | > 5 batches |

---

## Project structure

```
Industrial_Laundry/
├── ARCHITECTURE.md                  # Architecture decisions and dev guidelines
├── backend/                         # FastAPI service
│   ├── app/
│   │   ├── main.py                  # App factory, startup tasks
│   │   ├── core/
│   │   │   ├── config.py            # Settings via pydantic-settings
│   │   │   ├── database.py          # Async SQLAlchemy engine
│   │   │   └── redis.py             # Redis client + stream helpers
│   │   ├── api/v1/
│   │   │   ├── router.py
│   │   │   └── endpoints/
│   │   │       ├── events.py        # POST /events
│   │   │       ├── batches.py       # GET/POST /batches
│   │   │       ├── stations.py      # GET /stations
│   │   │       ├── alerts.py        # GET /alerts
│   │   │       └── manager.py       # GET /manager/overview (SSE)
│   │   ├── models/                  # SQLAlchemy ORM models
│   │   ├── schemas/                 # Pydantic request/response schemas
│   │   ├── services/
│   │   │   ├── event_processor.py   # Event business logic
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
│   └── pyproject.toml
├── station-app/                     # PWA for station tablets
│   └── src/
│       ├── components/              # BigButton, QRScanner, StatusBanner
│       └── services/
│           ├── localQueue.ts        # IndexedDB event queue
│           ├── syncEngine.ts        # Background sync + retry
│           ├── deviceConfig.ts      # VITE_STATION_ID validation
│           └── voiceAssist.ts       # ASR (augmentation only, never required)
├── dashboard/                       # Manager real-time dashboard
│   └── src/
│       ├── components/              # BottleneckPanel, StuckBatchAlert, ThroughputMeter
│       └── services/
│           └── sseClient.ts         # SSE connection + reconnect
├── infra/
│   ├── docker-compose.yml           # Production stack
│   ├── docker-compose.dev.yml       # Dev overrides (hot reload, exposed ports)
│   ├── docker-compose.infra.yml     # Infrastructure only (db, redis, observability)
│   ├── grafana/
│   ├── prometheus/
│   ├── nginx/
│   └── promtail/
├── scripts/
│   ├── seed.py                      # Dev data seeder (7 stations + batches)
│   ├── migrate.sh                   # Alembic migration runner
│   └── demo.ps1                     # End-to-end demo script
└── docs/
    ├── patterns.md                  # Code patterns — read before new files
    ├── workflows.md                 # Dev workflows
    └── demo.md                      # Demo guide
```

---

## Adding a new feature

```
New event type a worker creates?      → /new-event-type
New API endpoint?                     → /new-endpoint  (read docs/patterns.md first)
New database table?                   → /new-model     (creates model + Alembic migration)
New manager dashboard alert/metric?   → /new-alert
Non-obvious architecture choice?      → /adr           (document before you implement)
Not sure if code follows conventions? → /check-patterns
```

---

## Production readiness status

| Item | Status |
|------|--------|
| Consumer handles `UniqueViolation` (acks duplicate, no retry loop) | Done |
| PEL recovery on consumer restart (`xautoclaim`) | Done |
| AlertEngine queries filter by `tenant_id` | Done |
| Alembic initial migration (`001_initial_schema.py`) | Done |
| Redis down → fallback to direct PostgreSQL write | Done |
| Batch status updated to `completed` at final station | Done |
| Prometheus metrics defined + emitted | Done |
| `/metrics` endpoint mounted | Done |
| CORS origins configurable via env (`CORS_ORIGINS`) | Done |
| `VITE_STATION_ID` validated at startup (UUID check, clear error) | Done |
| Consumer isolated from API process (`worker` Docker service) | Done |
| Multi-tenant middleware (header → env → default) | Done |

---

## Design decisions

Key architecture decisions are documented as ADRs in [`architecture/adr/`](architecture/adr/). Read before overriding any existing decision.

| Decision | ADR |
|----------|-----|
| IndexedDB-first on station devices | ADR-002 |
| Redis Streams as event bus | ADR-003 |
| SSE (not WebSocket) for dashboard | ADR-004 |
| No authentication on station devices | ADR-005 |
| `tenant_id` on every query | ADR-006 |
| Voice as augmentation only | ADR-008 |
