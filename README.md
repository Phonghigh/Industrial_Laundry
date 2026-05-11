# Industrial Laundry — Operational Event Capture System

> "Software must blend into workflow. Workers don't adapt to software — software adapts to workers."

Low-friction operational event capture for industrial laundry facilities. Event-driven, offline-first, real-time operational visibility.

## Quick Start

```bash
# Full stack (production-like)
docker compose -f infra/docker-compose.yml up -d

# Dev mode (hot reload)
docker compose -f infra/docker-compose.yml -f infra/docker-compose.dev.yml up -d

# API docs (dev only)
open http://localhost:8000/docs

# Manager dashboard
open http://localhost:3001

# Grafana observability
open http://localhost:3000  # admin/admin
```

## Architecture

See [CLAUDE.md](CLAUDE.md) for full architecture, design decisions, and Claude Code guidelines.

## Services

| Service | Port | Purpose |
|---------|------|---------|
| FastAPI backend | 8000 | Event ingest, SSE stream |
| Station PWA | 3000 | Worker interaction app |
| Manager dashboard | 3001 | Real-time operational view |
| Grafana | 3000 | Observability |
| Prometheus | 9090 | Metrics |
| PostgreSQL | 5432 | Event store |
| Redis | 6379 | Event stream buffer |
