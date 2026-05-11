import { openDB, type IDBPDatabase } from "idb";

export interface QueuedEvent {
  localId: string;
  batchId: string;
  stationId: string;
  eventType: "started" | "completed" | "issue_flagged" | "skipped";
  deviceId: string;
  idempotencyKey: string;
  timestamp: string;
  metadata: Record<string, unknown>;
  syncStatus: "pending" | "synced" | "failed";
  retryCount: number;
}

const DB_NAME = "station_queue";
const STORE = "events";

async function getDb(): Promise<IDBPDatabase> {
  return openDB(DB_NAME, 1, {
    upgrade(db) {
      const store = db.createObjectStore(STORE, { keyPath: "localId" });
      store.createIndex("syncStatus", "syncStatus");
    },
  });
}

export async function enqueue(event: Omit<QueuedEvent, "syncStatus" | "retryCount">): Promise<void> {
  const db = await getDb();
  await db.put(STORE, { ...event, syncStatus: "pending", retryCount: 0 });
}

export async function getPending(): Promise<QueuedEvent[]> {
  const db = await getDb();
  return db.getAllFromIndex(STORE, "syncStatus", "pending");
}

export async function markSynced(localId: string): Promise<void> {
  const db = await getDb();
  const event = await db.get(STORE, localId);
  if (event) await db.put(STORE, { ...event, syncStatus: "synced" });
}

export async function incrementRetry(localId: string): Promise<void> {
  const db = await getDb();
  const event = await db.get(STORE, localId);
  if (event) await db.put(STORE, { ...event, retryCount: event.retryCount + 1 });
}
