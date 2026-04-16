"use client";

import { useEffect, useRef, useState } from "react";
import {
  describeScannerError,
  detectBarcodeScannerSupport,
  startBarcodeScanner,
  type ActiveBarcodeScannerSession,
} from "../lib/browser-barcode-scanner";
import { ModalShell } from "./modal-shell";

type BarcodeScannerDialogProps = {
  onDetected: (value: string) => void;
  onClose: () => void;
  mode?: "continuous" | "single";
  title?: string;
  description?: string;
};

function normalizeBarcodeInput(value: string) {
  return value.trim().replace(/[\s,]+/g, "");
}

export function BarcodeScannerDialog({
  onDetected,
  onClose,
  mode = "single",
  title = mode === "continuous" ? "Scan pantry items" : "Scan barcode",
  description = mode === "continuous"
    ? "Keep scanning to queue multiple barcodes. If the camera is unavailable, type or scan into the manual field instead."
    : "Pantry can use the browser camera when supported. If the camera is unavailable, type or scan into the manual field instead.",
}: BarcodeScannerDialogProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const manualInputRef = useRef<HTMLInputElement | null>(null);
  const scannerSessionRef = useRef<ActiveBarcodeScannerSession | null>(null);
  const lastDetectedRef = useRef<{ detectedAt: number; value: string } | null>(null);
  const onCloseRef = useRef(onClose);
  const onDetectedRef = useRef(onDetected);
  const [statusMessage, setStatusMessage] = useState("Checking browser support…");
  const [error, setError] = useState<string | null>(null);
  const [manualValue, setManualValue] = useState("");
  const [manualError, setManualError] = useState<string | null>(null);
  const [retryToken, setRetryToken] = useState(0);
  const [canRetryCamera, setCanRetryCamera] = useState(false);
  const [engineLabel, setEngineLabel] = useState<string | null>(null);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    onDetectedRef.current = onDetected;
  }, [onDetected]);

  function stopScanner() {
    scannerSessionRef.current?.stop();
    scannerSessionRef.current = null;
  }

  function commitBarcode(value: string) {
    const barcode = normalizeBarcodeInput(value);
    if (!barcode) {
      setManualError("Enter a barcode first.");
      manualInputRef.current?.focus();
      return;
    }

    const lastDetected = lastDetectedRef.current;
    const now = Date.now();
    if (mode === "continuous" && lastDetected && lastDetected.value === barcode && now - lastDetected.detectedAt < 1200) {
      return;
    }

    lastDetectedRef.current = {
      detectedAt: now,
      value: barcode,
    };

    setManualError(null);
    onDetectedRef.current(barcode);

    if (mode === "continuous") {
      setManualValue("");
      setStatusMessage(`Queued ${barcode}. Keep scanning or type the next barcode below.`);
      return;
    }

    onCloseRef.current();
  }

  useEffect(() => {
    if (!error) {
      return;
    }
    manualInputRef.current?.focus();
  }, [error]);

  useEffect(() => {
    let cancelled = false;

    async function initialiseScanner() {
      stopScanner();
      setError(null);
      setEngineLabel(null);
      setStatusMessage("Checking browser support…");

      const support = await detectBarcodeScannerSupport();
      if (cancelled) {
        return;
      }

      setCanRetryCamera(support.canRetry);

      if (!support.preferredEngine || support.permissionState === "denied") {
        setError(support.message);
        return;
      }

      setStatusMessage(support.message);

      const videoElement = videoRef.current;
      if (!videoElement) {
        return;
      }

      try {
        const session = await startBarcodeScanner({
          support,
          videoElement,
          onDetected: commitBarcode,
          onStatus: (message) => {
            if (!cancelled) {
              setStatusMessage(message);
            }
          },
        });

        if (cancelled) {
          session.stop();
          return;
        }

        scannerSessionRef.current = session;
        setEngineLabel(
          session.engine === "native" ? "Built-in browser scanner" : "Compatible browser scanner",
        );
      } catch (scannerError) {
        if (cancelled) {
          return;
        }

        stopScanner();
        setError(describeScannerError(scannerError));
      }
    }

    void initialiseScanner();

    return () => {
      cancelled = true;
      stopScanner();
    };
  }, [mode, retryToken]);

  return (
    <ModalShell title={title} description={description} onClose={onClose}>
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
            <div className="scanner-status-row">
              {engineLabel ? <span className="pill">{engineLabel}</span> : null}
              <p className="helper-text">{statusMessage}</p>
            </div>
          </div>
        )}

        <div className="scanner-manual-panel">
          <label className="field">
            <span>{mode === "continuous" ? "Type or scan barcodes" : "Type or scan barcode"}</span>
            <input
              ref={manualInputRef}
              value={manualValue}
              onChange={(event) => {
                setManualValue(event.target.value);
                if (manualError) {
                  setManualError(null);
                }
              }}
              onKeyDown={(event) => {
                if (event.key !== "Enter") {
                  return;
                }
                event.preventDefault();
                commitBarcode(manualValue);
              }}
              placeholder={mode === "continuous" ? "Scan a barcode and wait for Enter" : "5000111046244"}
              autoComplete="off"
              autoCorrect="off"
              spellCheck={false}
              inputMode="numeric"
            />
          </label>

          {manualError ? <p className="error-text">{manualError}</p> : null}

          <div className="scanner-manual-actions">
            <button type="button" className="primary-button" onClick={() => commitBarcode(manualValue)}>
              {mode === "continuous" ? "Queue barcode" : "Use barcode"}
            </button>
          </div>

          <p className="helper-text">
            USB barcode scanners usually act like a keyboard and finish with Enter, so this field
            stays reliable when camera scanning is unavailable or less practical.
          </p>
        </div>
      </div>
    </ModalShell>
  );
}
