# Code Conventions

Explicit rules for every layer. When in doubt, match what already exists.

---

## Python (Backend)

### Naming

| Thing | Convention | Example |
|-------|-----------|---------|
| Files | `snake_case` | `event_processor.py` |
| Classes | `PascalCase` | `AlertEngine` |
| Functions / methods | `snake_case` | `compute_operational_state` |
| Constants | `UPPER_SNAKE` | `MAX_RETRIES = 10` |
| SQLAlchemy models | `PascalCase`, singular | `OperationalEvent`, `Batch` |
| Pydantic schemas | `PascalCase` + suffix | `EventIngest`, `EventIngestResponse` |
| Router files | match the resource | `events.py` for `/events` routes |

### Async Rules

- Every route handler is `async def` — no exceptions
- Every DB call uses `await` — never call sync SQLAlchemy
- Use `AsyncSession` from `app.core.database.get_db` via `Depends`
- Never use `session.execute(...).scalars().all()` with lazy loads — always explicit `joinedload` or separate queries

### Database Queries

```python
# GOOD — explicit, async, includes tenant_id
result = await db.execute(
    select(OperationalEvent)
    .where(OperationalEvent.tenant_id == tenant_id)
    .where(OperationalEvent.batch_id == batch_id)
    .order_by(OperationalEvent.ts.desc())
    .limit(50)
)
events = result.scalars().all()

# BAD — missing tenant_id, lazy pattern
events = db.query(OperationalEvent).filter_by(batch_id=batch_id).all()
```

### API Responses

- Event ingest endpoints always return `202 Accepted` (not `201`)
- Never return raw ORM objects — always go through a Pydantic schema
- Error responses use FastAPI's `HTTPException`, never bare `return {"error": ...}`
- 409 Conflict = idempotency key already seen (not an error — treat as success client-side)

### Logging

```python
import structlog
log = structlog.get_logger()

# GOOD — structured, with context
log.info("event_ingested", event_id=str(event_id), batch_id=str(batch_id))
log.error("redis_publish_failed", error=str(exc), event_id=str(event_id))

# BAD
print(f"Event {event_id} ingested")
logging.info("event ingested")
```

### Error Handling

- Only catch exceptions you can handle or must translate
- Let unexpected exceptions propagate to FastAPI's global handler
- Do NOT swallow exceptions with bare `except: pass` — use `except Exception as exc: log.error(...)`

---

## TypeScript (Station App + Dashboard)

### Naming

| Thing | Convention | Example |
|-------|-----------|---------|
| Files (components) | `PascalCase.tsx` | `BigButton.tsx` |
| Files (services/hooks) | `camelCase.ts` | `localQueue.ts`, `useStationState.ts` |
| Components | `PascalCase` | `BigButton`, `QRScanner` |
| Hooks | `use` prefix | `useStationState`, `useSync` |
| Services | noun or verb-noun | `localQueue`, `syncEngine` |
| Types/interfaces | `PascalCase` | `QueuedEvent`, `OperationalState` |
| Constants | `UPPER_SNAKE` | `MAX_RETRIES` |

### Station App Specific Rules

1. **IndexedDB first, always.** `enqueue()` before any `fetch()`.
2. **Optimistic UI always.** Worker sees confirmation before `fetch()` resolves.
3. **No blocking spinners.** If you need a loading state, use a non-blocking indicator.
4. **Big touch targets.** All interactive elements ≥ 64px height. Workers have wet gloved hands.
5. **High contrast.** Minimum WCAG AA. Factory lighting is harsh.
6. **No navigation.** Station app has one screen. No menus, no routes.

```typescript
// GOOD — enqueue first, optimistic confirm
async function handleComplete(batchId: string) {
  const event = buildEvent(batchId, "completed");
  await enqueue(event);        // ← IndexedDB, instant
  showConfirmation();          // ← Worker sees this immediately
  // syncEngine picks it up in background
}

// BAD — network-first, blocks worker
async function handleComplete(batchId: string) {
  setLoading(true);
  await fetch("/api/v1/events", { body: ... }); // ← blocks on network
  setLoading(false);
  showConfirmation();
}
```

### Dashboard Specific Rules

1. **Show operational state, not raw data.** "Drying overloaded (38 min avg wait)" not "34 events in the last hour."
2. **SSE state is a full snapshot.** Replace state on each event, never merge/patch.
3. **Reconnect silently.** EventSource auto-reconnects; no "connection lost" banner unless silent for > 60s.

---

## SQL / Database

- All migrations via **Alembic** — never hand-edit tables in production
- All tables have `tenant_id UUID NOT NULL` with an index
- `operational_events` is insert-only — no UPDATE, no DELETE, ever
- Index naming: `idx_{table}_{column}` (e.g., `idx_events_batch_ts`)
- Use `TIMESTAMPTZ` for all timestamps (not `TIMESTAMP`)
- Use `UUID` as primary key (not serial integer)

---

## Git

- Branch naming: `feat/`, `fix/`, `chore/` prefixes (e.g., `feat/voice-augmentation`)
- Commit messages: imperative, present tense ("Add offline sync retry backoff")
- One logical change per commit
- PRs must include: what changed, why, how to test

---

## File Structure Rules

- New API endpoint → new file in `backend/app/api/v1/endpoints/` + register in `router.py`
- New SQLAlchemy model → new file in `backend/app/models/` + import in `models/__init__.py`
- New Pydantic schema → new file or add to existing file in `backend/app/schemas/`
- New service → new file in `backend/app/services/`
- New React component (station) → `station-app/src/components/`
- New React component (dashboard) → `dashboard/src/components/`
