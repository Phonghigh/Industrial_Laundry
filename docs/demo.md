# Demo Guide — Industrial Laundry Operational Event Capture System

> **Phú Quốc facility** · FastAPI + Redis Streams + PostgreSQL · Real-time SSE dashboard

---

## Quickstart (automated)

```powershell
# From the repo root — runs everything unattended
.\scripts\demo.ps1

# Stack already running + DB already seeded
.\scripts\demo.ps1 -SkipStart -SkipSeed
```

The script starts Docker, migrates the DB, seeds data, fires a full event sequence, and prints the alert state at every step. Skip to [What to watch for](#what-to-watch-for) to understand the output.

---

## Manual walkthrough

### Prerequisites

| Requirement | Version |
|-------------|---------|
| Docker Desktop | 4.x+ |
| PowerShell | 5.1+ (Windows built-in) |

All other dependencies (Python, Node, Redis, Postgres) run inside Docker.

---

### Step 1 — Start the stack

```powershell
docker compose -f infra/docker-compose.yml up -d
```

Services started:

| Service | Port | What it does |
|---------|------|--------------|
| `api` | 8000 | FastAPI backend |
| `worker` | — | Redis Streams consumer |
| `db` | 5432 | PostgreSQL 16 |
| `redis` | 6379 | Event bus |
| `grafana` | 3000 | Metrics dashboard |
| `prometheus` | 9090 | Metrics scraper |
| `loki` | 3100 | Log aggregation |

Wait for the API to be healthy:

```powershell
docker compose -f infra/docker-compose.yml ps
# api should show: (healthy)
```

Verify:
```powershell
curl http://localhost:8000/health
# {"status":"ok"}
```

---

### Step 2 — Migrate and seed

Run once per fresh database:

```powershell
# Apply schema migrations
docker compose -f infra/docker-compose.yml exec api alembic upgrade head

# Seed 7 stations + 5 in-progress batches
docker compose -f infra/docker-compose.yml exec api `
    sh -c "PYTHONPATH=/app python scripts/seed.py"
```

What gets created:

| Table | Records |
|-------|---------|
| `stations` | Intake, Sorting, Washing, Drying, Ironing, Packing, Dispatch |
| `batches` | BATCH_2041 … BATCH_2045 (status: in_progress) |
| `operational_events` | 5 `started` events (one per batch, seeded ~1 hour ago) |

---

### Step 3 — Resolve IDs

The API works with UUIDs. Resolve them once per session:

```powershell
$stations = Invoke-RestMethod http://localhost:8000/api/v1/stations
$batches  = Invoke-RestMethod http://localhost:8000/api/v1/batches

# Build a name → id map
$stn = @{}
foreach ($s in $stations) { $stn[$s.name] = $s.id }

$b2041 = ($batches | Where-Object batch_code -eq "BATCH_2041").id
$b2042 = ($batches | Where-Object batch_code -eq "BATCH_2042").id
```

---

### Step 4 — Baseline alert state

Before firing any events, check what the alert engine sees:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/alerts | ConvertTo-Json -Depth 5
```

**Expected:** All 5 batches show as `stuck_batches` (~60 min) because the seed events are old. `station_throughput` is empty — no completed events. Intake and Dispatch show `never_active: true`.

---

### Step 5 — BATCH_2041 moves through Washing

```powershell
# Worker arrives at Washing
Invoke-RestMethod http://localhost:8000/api/v1/events -Method POST `
  -ContentType "application/json" `
  -Body (ConvertTo-Json @{
    batch_id        = $b2041
    station_id      = $stn["Washing"]
    event_type      = "started"
    device_id       = "tablet-washing-01"
    idempotency_key = [guid]::NewGuid().ToString()
    timestamp       = (Get-Date -Format o)
    metadata        = @{}
  })
# → 202 Accepted  {"event_id":"...","queued":true}

# Worker completes Washing
Invoke-RestMethod http://localhost:8000/api/v1/events -Method POST `
  -ContentType "application/json" `
  -Body (ConvertTo-Json @{
    batch_id        = $b2041
    station_id      = $stn["Washing"]
    event_type      = "completed"
    device_id       = "tablet-washing-01"
    idempotency_key = [guid]::NewGuid().ToString()
    timestamp       = (Get-Date -Format o)
    metadata        = @{}
  })
```

**Pipeline trace:**
```
POST /events
  → Redis XADD operational_events   (immediate, 202 returned)
  → worker XREADGROUP                (consumer picks up within 5s)
  → PostgreSQL INSERT                (idempotency_key unique constraint)
  → XACK                             (entry removed from PEL)
```

---

### Step 6 — BATCH_2041 arrives at Drying (leave open)

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/events -Method POST `
  -ContentType "application/json" `
  -Body (ConvertTo-Json @{
    batch_id        = $b2041
    station_id      = $stn["Drying"]
    event_type      = "started"
    device_id       = "tablet-drying-01"
    idempotency_key = [guid]::NewGuid().ToString()
    timestamp       = (Get-Date -Format o)
    metadata        = @{}
  })
```

Check alerts:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/alerts | ConvertTo-Json -Depth 5
```

**Expected changes:**
- `BATCH_2041` **gone from `stuck_batches`** — its last event (Drying started) is seconds old
- `station_throughput` shows `Washing: 1` — one completed batch this hour
- `Washing` and `Drying` **gone from `inactive_stations`** — they have recent events

---

### Step 7 — BATCH_2042 flags a mechanical issue

```powershell
# Batch arrives
Invoke-RestMethod http://localhost:8000/api/v1/events -Method POST `
  -ContentType "application/json" `
  -Body (ConvertTo-Json @{
    batch_id        = $b2042
    station_id      = $stn["Washing"]
    event_type      = "started"
    device_id       = "tablet-washing-01"
    idempotency_key = [guid]::NewGuid().ToString()
    timestamp       = (Get-Date -Format o)
    metadata        = @{}
  })

# Worker taps FLAG ISSUE
Invoke-RestMethod http://localhost:8000/api/v1/events -Method POST `
  -ContentType "application/json" `
  -Body (ConvertTo-Json @{
    batch_id        = $b2042
    station_id      = $stn["Washing"]
    event_type      = "issue_flagged"
    device_id       = "tablet-washing-01"
    idempotency_key = [guid]::NewGuid().ToString()
    timestamp       = (Get-Date -Format o)
    metadata        = @{ issue_code = "MECH_JAM" }
  })
```

**What this shows:** The `issue_flagged` event counts as activity — BATCH_2042 has a recent event and won't appear as stuck immediately. The `issue_code` is stored in the JSONB `metadata` column for later analysis.

---

### Step 8 — BATCH_2041 completes Drying

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/events -Method POST `
  -ContentType "application/json" `
  -Body (ConvertTo-Json @{
    batch_id        = $b2041
    station_id      = $stn["Drying"]
    event_type      = "completed"
    device_id       = "tablet-drying-01"
    idempotency_key = [guid]::NewGuid().ToString()
    timestamp       = (Get-Date -Format o)
    metadata        = @{}
  })
```

Check alerts again — `station_throughput` now shows both Washing and Drying with 1 completed batch each.

---

### Step 9 — Idempotency test

Fire the same logical event twice with the same `idempotency_key`:

```powershell
$ikey = [guid]::NewGuid().ToString()

$body = @{
    batch_id        = $b2041
    station_id      = $stn["Drying"]
    event_type      = "completed"
    device_id       = "tablet-drying-01"
    idempotency_key = $ikey
    timestamp       = (Get-Date -Format o)
    metadata        = @{}
}

# First send
Invoke-RestMethod http://localhost:8000/api/v1/events -Method POST `
    -ContentType "application/json" -Body (ConvertTo-Json $body)

# Second send (simulate retry / network duplicate)
Invoke-RestMethod http://localhost:8000/api/v1/events -Method POST `
    -ContentType "application/json" -Body (ConvertTo-Json $body)
```

**Expected:** Both return `202`. The worker inserts the first, catches a `UniqueViolation` on the second, acks it silently. The DB has exactly one row for that `idempotency_key`.

Verify:
```powershell
docker compose -f infra/docker-compose.yml exec db `
    psql -U postgres industrial_laundry -c `
    "SELECT COUNT(*) FROM operational_events WHERE idempotency_key = '$ikey'::uuid;"
# count = 1
```

---

### Step 10 — Final state

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/alerts | ConvertTo-Json -Depth 5
```

**Final expected state:**

| Field | Value |
|-------|-------|
| `stuck_batches` | BATCH_2042–2045 (seed events only, no activity) |
| `station_throughput` | Washing: 1, Drying: 1 |
| `inactive_stations` | Ironing, Sorting, Packing (silent), Intake + Dispatch (never active) |

---

## What to watch for

### The event pipeline

Every `POST /events` returns `202 Accepted` instantly — the worker persists asynchronously:

```
Station tablet  ──POST──►  API  ──XADD──►  Redis Stream
                 ◄──202──                   │
                                        XREADGROUP
                                            │
                                        PostgreSQL INSERT
                                        (idempotency_key unique)
                                            │
                                        XACK
```

**Offline behaviour:** If the tablet loses Wi-Fi, events queue to IndexedDB and sync when connectivity returns — same idempotency key prevents duplicates.

### Alert thresholds (config defaults)

| Alert | Threshold | Config key |
|-------|-----------|------------|
| Stuck batch | 30 minutes | `STUCK_BATCH_THRESHOLD_MINS` |
| Inactive station | 15 minutes | `STATION_INACTIVITY_THRESHOLD_MINS` |

Override at runtime:
```powershell
docker compose -f infra/docker-compose.yml exec api `
    sh -c "STUCK_BATCH_THRESHOLD_MINS=1 python -c '
import asyncio, json
from app.services.alert_engine import AlertEngine
r = asyncio.run(AlertEngine().compute_operational_state())
print(json.dumps(r, indent=2, default=str))
'"
```

### Stuck-batch detection logic

The query uses `DISTINCT ON (batch_id)` to find **the single most recent event per batch across all stations**, then checks if that timestamp is older than the threshold. This means a batch moving from Sorting → Washing → Drying correctly shows its *current* station (Drying) not the old one (Sorting).

### Checking the DB directly

```powershell
# Recent events
docker compose -f infra/docker-compose.yml exec db `
    psql -U postgres industrial_laundry -c `
    "SELECT batch_id, station_id, event_type, ts FROM operational_events ORDER BY ts DESC LIMIT 10;"

# Redis stream health
docker compose -f infra/docker-compose.yml exec redis redis-cli XINFO GROUPS operational_events
```

---

## URL reference

| Interface | URL | Notes |
|-----------|-----|-------|
| API docs (Swagger) | http://localhost:8000/docs | Dev mode only |
| Alerts snapshot | http://localhost:8000/api/v1/alerts | JSON, no auth |
| Batches | http://localhost:8000/api/v1/batches | |
| Stations | http://localhost:8000/api/v1/stations | |
| Prometheus metrics | http://localhost:8000/metrics | |
| Grafana | http://localhost:3000 | admin / admin |
| Prometheus UI | http://localhost:9090 | |

---

## Teardown

```powershell
# Stop all containers
docker compose -f infra/docker-compose.yml down

# Stop and wipe all data (volumes)
docker compose -f infra/docker-compose.yml down -v
```
