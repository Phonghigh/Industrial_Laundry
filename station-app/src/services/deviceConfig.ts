/**
 * deviceConfig — validates environment config on app startup.
 *
 * Called once before the app mounts. Throws a clear error if required
 * env vars are missing or invalid so the problem surfaces immediately
 * during deployment, not silently at runtime.
 *
 * Required env vars (set in .env.local or Docker env):
 *   VITE_STATION_ID  — UUID of this physical station
 *   VITE_API_BASE    — Base URL of the backend API (optional, has default)
 */

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export interface DeviceConfig {
  stationId: string;
  apiBase: string;
  deviceId: string;
}

/**
 * Validate env vars and return a resolved DeviceConfig.
 * Throws with a human-readable message if anything is wrong —
 * the app should render an error screen and refuse to operate.
 */
export function resolveDeviceConfig(): DeviceConfig {
  const stationId = import.meta.env.VITE_STATION_ID as string | undefined;
  const apiBase = (import.meta.env.VITE_API_BASE as string | undefined) ?? "http://localhost:8000";

  if (!stationId) {
    throw new Error(
      "VITE_STATION_ID is not set.\n" +
      "Add VITE_STATION_ID=<station-uuid> to .env.local or Docker environment.\n" +
      "Each physical station device must have a unique station UUID."
    );
  }

  if (!UUID_RE.test(stationId)) {
    throw new Error(
      `VITE_STATION_ID "${stationId}" is not a valid UUID.\n` +
      "Expected format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    );
  }

  const deviceId = getOrCreateDeviceId();

  return { stationId, apiBase, deviceId };
}

/**
 * Device ID persists across page reloads in localStorage.
 * Generated once on first app load, never changes for this physical device.
 */
function getOrCreateDeviceId(): string {
  const key = "laundry_device_id";
  const existing = localStorage.getItem(key);
  if (existing && UUID_RE.test(existing)) {
    return existing;
  }
  const id = crypto.randomUUID();
  localStorage.setItem(key, id);
  return id;
}
