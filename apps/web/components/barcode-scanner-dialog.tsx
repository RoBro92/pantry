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

const BARCODE_FORMATS = ["ean_13", "ean_8", "upc_a", "upc_e", "code_128"];

export function BarcodeScannerDialog({
  onDetected,
  onClose,
}: BarcodeScannerDialogProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const frameRequestRef = useRef<number | null>(null);
  const detectorRef = useRef<InstanceType<BarcodeDetectorConstructor> | null>(null);
  const detectingRef = useRef(false);
  const [statusMessage, setStatusMessage] = useState("Starting the camera…");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function startScanner() {
      const detectorClass = (window as Window & {
        BarcodeDetector?: BarcodeDetectorConstructor;
      }).BarcodeDetector;

      if (!window.isSecureContext) {
        setError("Camera scanning needs a secure browser context. Type the barcode instead.");
        return;
      }
      if (!detectorClass || !navigator.mediaDevices?.getUserMedia) {
        setError("Camera barcode scanning is not available in this browser yet.");
        return;
      }

      try {
        detectorRef.current = new detectorClass({ formats: BARCODE_FORMATS });
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
        setStatusMessage("Point the camera at the barcode.");
        frameRequestRef.current = window.requestAnimationFrame(() => {
          void detectFrame();
        });
      } catch (requestError) {
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Could not start the barcode scanner.",
        );
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
          .map((result) => result.rawValue?.trim() ?? "")
          .find(Boolean);
        if (barcode) {
          onDetected(barcode);
          onClose();
          return;
        }
      } catch (requestError) {
        setError(
          requestError instanceof Error
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
      if (frameRequestRef.current !== null) {
        window.cancelAnimationFrame(frameRequestRef.current);
      }
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    };
  }, [onClose, onDetected]);

  return (
    <ModalShell
      title="Scan barcode"
      description="Pantry can use the browser camera when supported. USB scanners still work by typing directly into the barcode field."
      onClose={onClose}
    >
      {error ? (
        <div className="warning-callout">
          <strong>Camera scanning unavailable</strong>
          <p>{error}</p>
          <p>Type the barcode manually or use a USB barcode scanner in the field instead.</p>
        </div>
      ) : (
        <div className="stack">
          <div className="scanner-frame">
            <video ref={videoRef} className="scanner-video" muted playsInline />
          </div>
          <p className="helper-text">{statusMessage}</p>
        </div>
      )}
    </ModalShell>
  );
}
