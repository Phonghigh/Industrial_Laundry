import { useEffect, useRef } from "react";
import { enqueue, getPending, type QueuedEvent } from "./services/localQueue";
import { startSyncEngine } from "./services/syncEngine";
import { VoiceAssist } from "./services/voiceAssist";
import { BigButton } from "./components/BigButton";
import { StatusBanner } from "./components/StatusBanner";
import { QRScanner } from "./components/QRScanner";
import { useStationStore } from "./stores/stationStore";

const DEVICE_KEY = "laundry_device_id";

function getOrCreateDeviceId(): string {
  const existing = localStorage.getItem(DEVICE_KEY);
  if (existing) return existing;
  const id = crypto.randomUUID();
  localStorage.setItem(DEVICE_KEY, id);
  return id;
}

const DEVICE_ID = getOrCreateDeviceId();

const STATIONS = [
  { value: "station_intake_01", label: "1. INTAKE" },
  { value: "station_sorting_01", label: "2. SORTING" },
  { value: "station_washing_01", label: "3. WASHING" },
  { value: "station_drying_01", label: "4. DRYING" },
  { value: "station_ironing_01", label: "5. IRONING" },
  { value: "station_packing_01", label: "6. PACKING" },
  { value: "station_dispatch_01", label: "7. DISPATCH" },
];

export default function App() {
  const {
    stationId,
    batchCode,
    pendingCount,
    lastAction,
    scannerOpen,
    voiceListening,
    setStationId,
    setBatchCode,
    setPendingCount,
    flashAction,
    openScanner,
    closeScanner,
    setVoiceListening,
  } = useStationStore();

  const voiceRef = useRef<VoiceAssist | null>(null);

  // Start sync engine and pending-count poller
  useEffect(() => {
    const stopSync = startSyncEngine(2000);
    const interval = setInterval(async () => {
      const pending = await getPending();
      setPendingCount(pending.length);
    }, 1000);
    return () => {
      stopSync();
      clearInterval(interval);
    };
  }, [setPendingCount]);

  // Set up voice assist (augmentation only — silently skipped if unsupported)
  useEffect(() => {
    const va = new VoiceAssist(
      ({ transcript }) => {
        setBatchCode(transcript);
        flashAction(`Voice: ${transcript}`);
        setVoiceListening(false);
      },
      () => {
        flashAction("LOW CONFIDENCE — PLEASE USE BUTTON OR TYPE BATCH CODE");
        setVoiceListening(false);
      }
    );
    voiceRef.current = va;
    return () => va.destroy();
  }, [setBatchCode, flashAction, setVoiceListening]);

  const handleEvent = async (type: QueuedEvent["eventType"]) => {
    if (!batchCode.trim()) {
      flashAction("⚠ PLEASE ENTER OR SCAN A BATCH CODE");
      return;
    }

    await enqueue({
      localId: crypto.randomUUID(),
      batchId: batchCode.trim().toUpperCase(),
      stationId,
      eventType: type,
      deviceId: DEVICE_ID,
      idempotencyKey: crypto.randomUUID(),
      timestamp: new Date().toISOString(),
      metadata: { source: "pwa_ui" },
    });

    flashAction(`Logged: ${type.toUpperCase()} — ${batchCode.toUpperCase()}`);

    if (type === "completed" || type === "skipped") {
      setBatchCode("");
    }

    const pending = await getPending();
    setPendingCount(pending.length);
  };

  const handleVoiceToggle = () => {
    const va = voiceRef.current;
    if (!va?.isSupported) {
      flashAction("VOICE NOT SUPPORTED ON THIS DEVICE");
      return;
    }
    if (voiceListening) {
      va.stop();
      setVoiceListening(false);
    } else {
      va.start();
      setVoiceListening(true);
    }
  };

  const handleQRScan = (code: string) => {
    setBatchCode(code);
    closeScanner();
    flashAction(`Scanned: ${code}`);
  };

  return (
    <div className="station-wrapper">
      <StatusBanner deviceId={DEVICE_ID} pendingCount={pendingCount} lastAction={lastAction} />

      {scannerOpen && <QRScanner onScan={handleQRScan} onClose={closeScanner} />}

      <section className="setup-panel">
        <div className="input-group">
          <label htmlFor="station-select">Active Station</label>
          <select
            id="station-select"
            className="touch-input"
            value={stationId}
            onChange={(e) => setStationId(e.target.value)}
          >
            {STATIONS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </div>

        <div className="input-group">
          <label htmlFor="batch-input">BATCH CODE</label>
          <div className="batch-input-row">
            <input
              id="batch-input"
              className="touch-input"
              placeholder="BATCH_XXXX"
              autoComplete="off"
              value={batchCode}
              onChange={(e) => setBatchCode(e.target.value.toUpperCase())}
            />
            <button
              className="icon-btn"
              onClick={openScanner}
              title="Scan QR code"
              aria-label="Open QR scanner"
            >
              ▦
            </button>
            {voiceRef.current?.isSupported && (
              <button
                className={`icon-btn ${voiceListening ? "icon-btn--active" : ""}`}
                onClick={handleVoiceToggle}
                title={voiceListening ? "Stop listening" : "Speak batch code"}
                aria-label={voiceListening ? "Stop voice input" : "Start voice input"}
              >
                {voiceListening ? "⏹" : "🎤"}
              </button>
            )}
          </div>
        </div>
      </section>

      <main className="actions-grid">
        <BigButton
          variant="start"
          icon="▶"
          label="START BATCH"
          subtext="Begin operation on station"
          disabled={!batchCode}
          onClick={() => handleEvent("started")}
        />
        <BigButton
          variant="complete"
          icon="✔"
          label="COMPLETE BATCH"
          subtext="Finish & push to next stage"
          disabled={!batchCode}
          onClick={() => handleEvent("completed")}
        />
        <BigButton
          variant="issue"
          icon="⚠"
          label="FLAG ISSUE / JAM"
          subtext="Report delay / mechanical alert"
          disabled={!batchCode}
          onClick={() => handleEvent("issue_flagged")}
        />
      </main>
    </div>
  );
}
