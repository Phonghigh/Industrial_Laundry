# Failure Mode Analysis

The system must continue operating under every common failure. Stations never stop.

## Failure Matrix

| Failure | Immediate Behaviour | Worker Impact | Recovery |
|---------|--------------------|----|----------|
| Wi-Fi lost | Events queued in IndexedDB | None — UI confirms instantly | Auto-sync when network restores |
| ASR confidence < 0.75 | Re-prompt worker or fall back to button | One extra tap | Worker taps big button |
| ASR service down | Silent fallback to QR/button only | None visible | Log error, alert ops |
| Device reboot | IndexedDB persists across reboot | Station briefly dark | App loads, resumes sync queue |
| Redis down | API writes direct to PostgreSQL | None (slower ingest) | Redis consumer replays on restart |
| PostgreSQL slow | Redis buffers events | None | Scale read replica, adjust pool |
| Backend deploy | Station queues during gap | None (< 10s gap) | Rolling restart absorbs |
| Dashboard crash | Zero impact on stations | None | SSE client auto-reconnects |
| Complete network partition | All stations queue locally | None | Bulk sync on restore |

## Station App Resilience Rules

1. **Optimistic UI always.** Worker sees confirmation before any network call.
2. **IndexedDB is the source of truth on device.** Never rely on network state.
3. **Idempotency keys prevent duplicates.** Safe to retry any event infinitely.
4. **No auth on station devices.** Shared, mounted, always-on. No login = no lockout.
5. **Minimal UI.** No loading states that block the worker. Big buttons, high contrast.

## Alert Priority

| Priority | Condition | Action |
|----------|-----------|--------|
| P1 | Station silent > 15 min | Page on-site supervisor |
| P1 | Batch stuck > 30 min | Page floor manager |
| P2 | sync_failure_rate > 2% | Alert ops team |
| P2 | Device offline > 1 | Alert ops team |
| P3 | ASR confidence avg < 0.85 | Log, weekly review |
| P3 | Redis backlog > 500 | Ops review |
