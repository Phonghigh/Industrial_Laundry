Feat/**
 * QR Scanner overlay — tap the scan icon to open, point camera at batch label.
 * Uses jsqr for frame-by-frame decoding (no external service, works offline).
 * Fires onScan(code) as soon as a QR code is detected, then closes itself.
 */

import { useEffect, useRef, useState } from "react";
import jsQR from "jsqr";

interface QRScannerProps {
  onScan: (code: string) => void;
  onClose: () => void;
}

export function QRScanner({ onScan, onClose }: QRScannerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const rafRef = useRef<number>(0);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    let mounted = true;

    async function startCamera() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "environment", width: { ideal: 1280 } },
          audio: false,
        });
        streamRef.current = stream;

        if (videoRef.current && mounted) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play();
          rafRef.current = requestAnimationFrame(scanFrame);
        }
      } catch {
        setError("CAMERA ACCESS DENIED — TAP CLOSE AND ENTER BATCH CODE MANUALLY");
      }
    }

    function scanFrame() {
      if (!mounted) return;

      const video = videoRef.current;
      const canvas = canvasRef.current;
      if (!video || !canvas || video.readyState < video.HAVE_ENOUGH_DATA) {
        rafRef.current = requestAnimationFrame(scanFrame);
        return;
      }

      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;

      const ctx = canvas.getContext("2d", { willReadFrequently: true });
      if (!ctx) return;

      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      const code = jsQR(imageData.data, imageData.width, imageData.height, {
        inversionAttempts: "dontInvert",
      });

      if (code?.data) {
        onScan(code.data.trim().toUpperCase());
        return; // caller will close the scanner
      }

      rafRef.current = requestAnimationFrame(scanFrame);
    }

    startCamera();

    return () => {
      mounted = false;
      cancelAnimationFrame(rafRef.current);
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, [onScan]);

  return (
    <div className="qr-overlay" role="dialog" aria-label="QR Code Scanner">
      <div className="qr-frame">
        <div className="qr-header">
          <span className="qr-title">SCAN BATCH QR CODE</span>
          <button className="qr-close touch-btn" onClick={onClose} aria-label="Close scanner">
            ✕ CLOSE
          </button>
        </div>

        {error ? (
          <p className="qr-error">{error}</p>
        ) : (
          <>
            <video
              ref={videoRef}
              className="qr-video"
              playsInline
              muted
              aria-label="Camera preview"
            />
            <canvas ref={canvasRef} className="qr-canvas" aria-hidden="true" />
            <p className="qr-hint">Point camera at QR label on batch bag</p>
          </>
        )}
      </div>
    </div>
  );
}
