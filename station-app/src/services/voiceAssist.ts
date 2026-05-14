/**
 * Voice assist — augmentation only (ADR-008).
 *
 * Wraps the Web Speech API. Workers can speak a batch code instead of typing,
 * but the button workflow is always available as fallback. Never required.
 *
 * Confidence threshold (0.75) matches settings.asr_confidence_min on the backend.
 * Below threshold → onLowConfidence fires so the UI prompts button fallback.
 */

export interface VoiceResult {
  transcript: string;
  confidence: number;
}

export type VoiceResultCallback = (result: VoiceResult) => void;
export type LowConfidenceCallback = () => void;

const CONFIDENCE_THRESHOLD = 0.75;

// Phú Quốc facility — Vietnamese primary, English secondary
const PREFERRED_LANGS = ["vi-VN", "en-US"];

declare global {
  interface Window {
    SpeechRecognition: typeof SpeechRecognition;
    webkitSpeechRecognition: typeof SpeechRecognition;
  }
}

export class VoiceAssist {
  private recognition: SpeechRecognition | null = null;
  private onResult: VoiceResultCallback;
  private onLowConfidence: LowConfidenceCallback;
  private _listening = false;

  constructor(onResult: VoiceResultCallback, onLowConfidence: LowConfidenceCallback) {
    this.onResult = onResult;
    this.onLowConfidence = onLowConfidence;

    const SpeechRecognitionImpl =
      window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognitionImpl) return;

    this.recognition = new SpeechRecognitionImpl();
    this.recognition.continuous = false;
    this.recognition.interimResults = false;
    this.recognition.maxAlternatives = 1;
    this.recognition.lang = PREFERRED_LANGS[0];

    this.recognition.onresult = (event: SpeechRecognitionEvent) => {
      const alt = event.results[0][0];
      const confidence = alt.confidence ?? 1.0; // some browsers omit confidence
      const transcript = alt.transcript.trim().toUpperCase();

      if (confidence < CONFIDENCE_THRESHOLD) {
        this.onLowConfidence();
      } else {
        this.onResult({ transcript, confidence });
      }
    };

    this.recognition.onend = () => {
      this._listening = false;
    };

    this.recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      // "no-speech" is normal; all others logged but silenced to avoid breaking UI
      if (event.error !== "no-speech") {
        console.warn("[VoiceAssist] error:", event.error);
      }
      this._listening = false;
    };
  }

  get isSupported(): boolean {
    return this.recognition !== null;
  }

  get listening(): boolean {
    return this._listening;
  }

  start(): void {
    if (!this.recognition || this._listening) return;
    this._listening = true;
    this.recognition.start();
  }

  stop(): void {
    if (!this.recognition || !this._listening) return;
    this.recognition.stop();
    // _listening set to false in onend handler
  }

  destroy(): void {
    this.stop();
    this.recognition = null;
  }
}
