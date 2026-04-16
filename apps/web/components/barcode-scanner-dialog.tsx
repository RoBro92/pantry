"use client";

import { useEffect, useRef, useState } from "react";
import { ModalShell } from "./modal-shell";

type BarcodeScannerDialogProps = {
  onDetected: (value: string) => void;
  onClose: () => void;
};

type BarcodeDetectionResult = {
  rawValue?: string;
};

type BarcodeDetectorConstructor = new (options?: {
  formats?: string[];
}) => {
  detect: (source: HTMLVideoElement) => Promise<BarcodeDetectionResult[]>;
};

type BarcodeDetectorStatic = BarcodeDetectorConstructor & {
  getSupportedFormats?: () => Promise<string[]>;
};

const BARCODE_FORMATS = ["ean_13", "ean_8", "upc_a", "upc_e", "code_128"];

function normalizeBarcodeInput(value: string) {
  return value.trim().replace(/[\s,]+/g, "");
}

function describeScannerError(error: unknown) {
  if (error instanceof DOMException) {
    if (error.name === "NotAllowedError") {
      return "Camera access was blocked. Allow camera permission or type the barcode instead.";
    }
    if (error.name === "NotFoundError") {
      return "No camera was found on this device.";
    }
    if (error.name === "NotReadableError") {
      return "The camera is already in use by another application or browser tab.";
    }
    if (error.name === "OverconstrainedError") {
      return "This camera could not satisfy Pantry's barcode scanning request.";
    }
  }
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return "Could not start the barcode scanner.";
}

export function BarcodeScannerDialog({
  onDetected,
  onClose,
}: BarcodeScannerDialogProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const manualInputRef = useRef<HTMLInputElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const frameRequestRef = useRef<number | null>(null);
  const detectorRef = useRef<InstanceType<BarcodeDetectorConstructor> | null>(null);
  const detectingRef = useRef(false);
  const [statusMessage, setStatusMessage] = useState("Checking browser support…");
  const [error, setError] = useState<string | null>(null);
  const [manualValue, setManualValue] = useState("");
  const [manualError, setManualError] = useState<string | null>(null);
  const [retryToken, setRetryToken] = useState(0);
  const [canRetryCamera, setCanRetryCamera] = useState(false);

  function stopScanner() {
    if (frameRequestRef.current !== null) {
      window.cancelAnimationFrame(frameRequestRef.current);
      frameRequestRef.current = null;
    }
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }

  function commitManualValue() {
    const barcode = normalizeBarcodeInput(manualValue);
    if (!barcode) {
      setManualError("Enter a barcode first.");
      manualInputRef.current?.focus();
      return;
    }
    setManualError(null);
    onDetected(barcode);
    onClose();
  }

  useEffect(() => {
    if (!error) {
      return;
    }
    manualInputRef.current?.focus();
  }, [error]);

  useEffect(() => {
    let cancelled = false;

    async function startScanner() {
      setError(null);
      setCanRetryCamera(false);
      setStatusMessage("Checking browser support…");

      const detectorClass = (window as Window & {
        BarcodeDetector?: BarcodeDetectorStatic;
      }).BarcodeDetector;

      if (!window.isSecureContext) {
        setError(
          "Camera scanning needs HTTPS or localhost in a secure browser context.",
        );
        return;
      }
      if (!detectorClass || !navigator.mediaDevices?.getUserMedia) {
        setError(
          "This browser does not expose camera barcode scanning yet.",
        );
        return;
      }

      setCanRetryCamera(true);

      let supportedFormats = BARCODE_FORMATS;
      if (typeof detectorClass.getSupportedFormats === "function") {
        try {
          const browserFormats = await detectorClass.getSupportedFormats();
          supportedFormats = BARCODE_FORMATS.filter((format) =>
            browserFormats.includes(format),
          );
        } catch {
          supportedFormats = BARCODE_FORMATS;
        }
      }

      if (supportedFormats.length === 0) {
        setCanRetryCamera(false);
        setError(
          "This browser can open the camera, but it does not expose barcode formats Pantry can read.",
        );
        return;
      }

      try {
        detectorRef.current = new detectorClass({ formats: supportedFormats });
        setStatusMessage("Requesting camera permission…");
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: false,
          video: {
            facingMode: { ideal: "environment" },
          },
        });
        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }

        streamRef.current = stream;
        const video = videoRef.current;
        if (!video) {
          return;
        }
        video.srcObject = stream;
        await video.play();
        setStatusMessage("Point the camera at the barcode, or type it below.");
        frameRequestRef.current = window.requestAnimationFrame(() => {
          void detectFrame();
        });
      } catch (requestError) {
        stopScanner();
        setError(describeScannerError(requestError));
      }
    }

    async function detectFrame() {
      if (detectingRef.current) {
        frameRequestRef.current = window.requestAnimationFrame(() => {
          void detectFrame();
        });
        return;
      }
      const detector = detectorRef.current;
      const video = videoRef.current;
      if (!detector || !video) {
        return;
      }
      if (video.readyState < HTMLMediaElement.HAVE_ENOUGH_DATA) {
        frameRequestRef.current = window.requestAnimationFrame(() => {
          void detectFrame();
        });
        return;
      }

      detectingRef.current = true;
      try {
        const results = await detector.detect(video);
        const barcode = results
          .map((result) => normalizeBarcodeInput(result.rawValue ?? ""))
          .find(Boolean);
        if (barcode) {
          onDetected(barcode);
          onClose();
          return;
        }
      } catch (requestError) {
        stopScanner();
        setError(
          requestError instanceof Error && requestError.message.trim()
            ? requestError.message
            : "Camera barcode scanning failed.",
        );
        return;
      } finally {
        detectingRef.current = false;
      }

      frameRequestRef.current = window.requestAnimationFrame(() => {
        void detectFrame();
      });
    }

    void startScanner();
    return () => {
      cancelled = true;
      stopScanner();
    };
  }, [onClose, onDetected, retryToken]);

  return (
    <ModalShell
      title="Scan barcode"
      description="Pantry can use the browser camera when supported. If the camera is unavailable, type or scan into the manual field instead."
      onClose={onClose}
    >
      <div className="stack" data-testid="barcode-scanner-dialog">
        {error ? (
          <div className="warning-callout">
            <strong>Camera scanning unavailable</strong>
            <p>{error}</p>
            {canRetryCamera ? (
              <div className="page-actions">
                <button
                  type="button"
                  className="ghost-button compact-button"
                  onClick={() => setRetryToken((current) => current + 1)}
                >
                  Try camera again
                </button>
              </div>
            ) : null}
          </div>
        ) : (
          <div className="stack">
            <div className="scanner-frame">
              <video ref={videoRef} className="scanner-video" muted playsInline />
            </div>
            <p className="helper-text">{statusMessage}</p>
          </div>
        )}

        <div className="scanner-manual-panel">
          <label className="field">
            <span>Type or scan barcode</span>
            <input
              ref={manualInputRef}
              value={manualValue}
              onChange={(event) => {
                setManualValue(event.target.value);
                setManualError(null);
              }}
              onKeyDown={(event) => {
                if (event.key !== "Enter") {
                  return;
                }
                event.preventDefault();
                commitManualValue();
              }}
              placeholder="5000111046244"
              autoComplete="off"
              autoCorrect="off"
              spellCheck={false}
            />
          </label>
          <div className="scanner-manual-actions">
            <button
              type="button"
              className="primary-button"
              disabled={!normalizeBarcodeInput(manualValue)}
              onClick={commitManualValue}
            >
              Use barcode
            </button>
          </div>
          <p className="helper-text">
            USB barcode scanners usually act like a keyboard and finish with Enter, so this field
            works well on desktop too.
          </p>
          {manualError ? <p className="error-text">{manualError}</p> : null}
        </div>
      </div>
    </ModalShell>
  );
}
