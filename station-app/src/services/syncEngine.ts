import { getPending, markSynced, incrementRetry, type QueuedEvent } from "./localQueue";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";
const MAX_RETRIES = 10;
const BACKOFF_BASE_MS = 1000;

async function syncEvent(event: QueuedEvent): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        batch_id: event.batchId,
        station_id: event.stationId,
        event_type: event.eventType,
        device_id: event.deviceId,
        idempotency_key: event.idempotencyKey,
        timestamp: event.timestamp,
        metadata: event.metadata,
      }),
    });
    return res.status === 202 || res.status === 409; // 409 = already processed (idempotent)
  } catch {
    return false;
  }
}

export async function runSyncCycle(): Promise<void> {
  const pending = await getPending();
  for (const event of pending) {
    if (event.retryCount >= MAX_RETRIES) continue;
    const success = await syncEvent(event);
    if (success) {
      await markSynced(event.localId);
    } else {
      await incrementRetry(event.localId);
    }
  }
}

export function startSyncEngine(intervalMs = 3000): () => void {
  const id = setInterval(runSyncCycle, intervalMs);
  runSyncCycle(); // immediate first attempt
  return () => clearInterval(id);
}
