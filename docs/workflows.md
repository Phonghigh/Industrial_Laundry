# Development Workflows

## Starting the stack

### Local dev (recommended — no Docker build)

Only infra runs in Docker (Postgres, Redis, Grafana, Prometheus, Loki).
API and frontends start natively — no image build, no slow pull.

```bash
# 1. Start infra only
docker compose -f infra/docker-compose.infra.yml up -d

# 2. Apply migrations + seed
bash scripts/migrate.sh
cd backend && python scripts/seed.py

# 3. Start API (new terminal)
cd backend && uvicorn app.main:app --reload --port 8000

# 4. Start Dashboard (new terminal)
cd dashboard && npm run dev

# 5. Start Station app (new terminal)
cd station-app && npm run dev
```

In this mode `RUN_CONSUMER_IN_PROCESS` defaults to `false` — the stream consumer
runs as an asyncio task inside uvicorn automatically when `ENVIRONMENT=development`.
Set `RUN_CONSUMER_IN_PROCESS=true` in your shell if you need to force it:

```bash
# backend terminal
RUN_CONSUMER_IN_PROCESS=true uvicorn app.main:app --reload --port 8000
```

### Full Docker stack (production-like)

```bash
# Full stack (API + frontends built in Docker)
docker compose -f infra/docker-compose.yml -f infra/docker-compose.dev.yml up -d

# Check all services healthy
docker compose -f infra/docker-compose.yml ps

# Tail API logs
docker compose -f infra/docker-compose.yml logs -f api

# Apply migrations + seed
bash scripts/migrate.sh
cd backend && python scripts/seed.py
```

## Adding a new feature — checklist

For any non-trivial feature, work in this order:

1. **Does it change the event schema?** → Update `docs/event-schema.md` first
2. **Does it need a new table?** → Write the Alembic migration first, apply it, then write the model
3. **Does it need a new API endpoint?** → Write Pydantic schema → handler → register in router
4. **Does it need a new alert?** → Add method to `AlertEngine`, update SSE payload, update dashboard consumer
5. **Does it change worker interaction?** → Test on the station app UI; < 2s interaction rule applies

## Adding a new event type

1. Update `event_type` union in `station-app/src/services/localQueue.ts`
2. Update Pydantic schema regex in `backend/app/schemas/event.py`
3. Add button/trigger in station app UI
4. Document payload in `docs/event-schema.md`
5. Write a unit test for the new event type in `backend/tests/unit/`

## Adding a new station

Stations are data, not code. To add a new station:
1. Insert a row in the `stations` table (or add to `scripts/seed.py` for dev)
2. Assign a `sequence_order`
3. No code changes required unless the station has unique behaviour

## Running tests

```bash
cd backend
pytest tests/unit/ -v                 # fast, no DB
pytest tests/integration/ -v          # requires running DB + Redis
pytest tests/ --cov=app --cov-report=term-missing
```

Integration tests require:
```bash
docker compose -f infra/docker-compose.yml up -d db redis
```

## Checking code quality

```bash
cd backend
ruff check app/               # lint
ruff format app/ --check      # format check
mypy app/                     # type check
```

## Deploying to factory

```bash
# Build fresh images
docker compose -f infra/docker-compose.yml build

# Pull + restart services (zero-downtime for API via rolling restart)
docker compose -f infra/docker-compose.yml up -d --no-deps api

# Apply migrations before restarting API
bash scripts/migrate.sh
docker compose -f infra/docker-compose.yml restart api
```

## Observability

- **Grafana:** http://localhost:3000 (admin/admin)
- **Prometheus:** http://localhost:9090
- **API docs:** http://localhost:8000/docs (dev only)
- **API health:** `curl http://localhost:8000/health`

Key Grafana queries:
```promql
# Event ingest rate
rate(laundry_events_ingested_total[5m])

# P99 ingest latency
histogram_quantile(0.99, rate(laundry_event_ingest_latency_seconds_bucket[5m]))

# Redis stream backlog
laundry_redis_stream_backlog
```

## Debugging a stuck batch

```sql
-- Find all events for a batch
SELECT e.event_type, s.name as station, e.ts, e.device_id
FROM operational_events e
JOIN stations s ON e.station_id = s.id
WHERE e.batch_id = (SELECT id FROM batches WHERE batch_code = 'BATCH_2041')
ORDER BY e.ts;

-- Find batches with no events in last 30 min
SELECT b.batch_code, MAX(e.ts), NOW() - MAX(e.ts) as idle_for
FROM batches b
JOIN operational_events e ON e.batch_id = b.id
WHERE b.status = 'in_progress'
GROUP BY b.batch_code
HAVING MAX(e.ts) < NOW() - INTERVAL '30 minutes';
```

## Debugging sync failures

```bash
# Check device sync queue in browser DevTools
# Open: Application → IndexedDB → station_queue → events
# Filter: syncStatus = "pending" or "failed"

# Check sync engine logs in browser console
# Look for: "sync failed", "retry count"

# Verify API is reachable from device
curl http://<factory-ip>:8000/health
```
