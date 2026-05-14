"""
Prometheus metrics definitions for the Industrial Laundry API.

All metric names are prefixed with `laundry_`.
Units are included in the name (_seconds, _total, _count).

Import the metric objects directly from this module to record values:

    from app.middleware.observability import events_ingested_total
    events_ingested_total.labels(event_type="completed", path="redis").inc()

The /metrics endpoint is mounted in main.py via prometheus_client.make_asgi_app().
"""

from prometheus_client import Counter, Gauge, Histogram

# ── Event ingestion ────────────────────────────────────────────────────────

events_ingested_total = Counter(
    "laundry_events_ingested_total",
    "Total operational events received by the API",
    ["event_type", "path"],   # path = "redis" | "direct_db" | "duplicate"
)

event_ingest_latency_seconds = Histogram(
    "laundry_event_ingest_latency_seconds",
    "End-to-end latency of POST /api/v1/events (seconds)",
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
)

# ── Redis Stream ───────────────────────────────────────────────────────────

redis_stream_backlog = Gauge(
    "laundry_redis_stream_backlog",
    "Approximate number of unprocessed entries in the Redis stream",
)

# ── Sync reliability ───────────────────────────────────────────────────────

sync_failures_total = Counter(
    "laundry_sync_failures_total",
    "Total sync failures reported by station devices (4xx/5xx from POST /events)",
)

# ── Operational state ──────────────────────────────────────────────────────

stuck_batches_gauge = Gauge(
    "laundry_stuck_batches",
    "Number of in-progress batches currently flagged as stuck",
)

inactive_stations_gauge = Gauge(
    "laundry_inactive_stations",
    "Number of stations currently flagged as inactive",
)

# ── ASR ────────────────────────────────────────────────────────────────────

asr_confidence_histogram = Histogram(
    "laundry_asr_confidence_score",
    "Distribution of ASR confidence scores for voice-triggered events",
    buckets=[0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0],
)

# ── Device / connectivity ──────────────────────────────────────────────────

device_offline_count = Gauge(
    "laundry_device_offline_count",
    "Number of station devices that have not synced in the last 10 minutes",
)
