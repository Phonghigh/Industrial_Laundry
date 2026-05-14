export type EventType = "started" | "completed" | "issue_flagged" | "skipped";

export interface StationEvent {
  localId: string;
  batchId: string;
  stationId: string;
  eventType: EventType;
  deviceId: string;
  idempotencyKey: string;
  timestamp: string;
  metadata: Record<string, unknown>;
}
