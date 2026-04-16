"use client";

import type { IScannerControls } from "@zxing/browser";

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

export type BarcodeScannerPermissionState = "denied" | "granted" | "prompt" | "unknown";

export type BarcodeScannerEngine = "native" | "zxing";

export type BarcodeScannerSupportReason =
  | "camera_permission_denied"
  | "insecure_context"
  | "media_devices_unavailable"
  | "native_formats_unavailable";

export type BarcodeScannerSupport = {
  preferredEngine: BarcodeScannerEngine | null;
  fallbackEngine: BarcodeScannerEngine | null;
  permissionState: BarcodeScannerPermissionState;
  reason: BarcodeScannerSupportReason | null;
  message: string;
  nativeSupportedFormats: string[];
  canRetry: boolean;
};

type NativeScannerSession = {
  detector: InstanceType<BarcodeDetectorConstructor>;
  stream: MediaStream;
};

export type ActiveBarcodeScannerSession = {
  engine: BarcodeScannerEngine;
  stop: () => void;
};

type StartBarcodeScannerOptions = {
  support: BarcodeScannerSupport;
  videoElement: HTMLVideoElement;
  onDetected: (barcode: string) => void;
  onStatus?: (message: string) => void;
};

const NATIVE_BARCODE_FORMATS = ["ean_13", "ean_8", "upc_a", "upc_e", "code_128"] as const;

let zxingBrowserModulePromise: Promise<typeof import("@zxing/browser")> | null = null;
let zxingLibraryModulePromise: Promise<typeof import("@zxing/library")> | null = null;

function getBarcodeDetector() {
  return (window as Window & {
    BarcodeDetector?: BarcodeDetectorStatic;
  }).BarcodeDetector;
}

function clearVideoElement(videoElement: HTMLVideoElement) {
  videoElement.pause();
  videoElement.srcObject = null;
}

function getPreferredCameraConstraints(): MediaTrackConstraints {
  return {
    facingMode: { ideal: "environment" },
  };
}

function normalizeBarcodeValue(value: string) {
  return value.trim().replace(/[\s,]+/g, "");
}

function shouldRetryWithDefaultCamera(error: unknown) {
  return error instanceof DOMException && error.name === "OverconstrainedError";
}

async function queryCameraPermission(): Promise<BarcodeScannerPermissionState> {
  const permissionsApi = navigator.permissions as Permissions & {
    query?: (descriptor: { name: string }) => Promise<PermissionStatus>;
  };

  if (typeof permissionsApi.query !== "function") {
    return "unknown";
  }

  try {
    const permissionStatus = await permissionsApi.query({ name: "camera" });
    if (
      permissionStatus.state === "granted" ||
      permissionStatus.state === "prompt" ||
      permissionStatus.state === "denied"
    ) {
      return permissionStatus.state;
    }
  } catch {
    return "unknown";
  }

  return "unknown";
}

async function getSupportedNativeFormats(detectorClass: BarcodeDetectorStatic | undefined) {
  if (!detectorClass) {
    return [];
  }

  if (typeof detectorClass.getSupportedFormats !== "function") {
    return [...NATIVE_BARCODE_FORMATS];
  }

  try {
    const browserFormats = await detectorClass.getSupportedFormats();
    return NATIVE_BARCODE_FORMATS.filter((format) => browserFormats.includes(format));
  } catch {
    return [...NATIVE_BARCODE_FORMATS];
  }
}

async function openCameraStream() {
  try {
    return await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: getPreferredCameraConstraints(),
    });
  } catch (error) {
    if (!shouldRetryWithDefaultCamera(error)) {
      throw error;
    }

    return navigator.mediaDevices.getUserMedia({
      audio: false,
      video: true,
    });
  }
}

async function startNativeBarcodeScanner({
  detectorClass,
  supportedFormats,
  videoElement,
}: {
  detectorClass: BarcodeDetectorStatic;
  supportedFormats: string[];
  videoElement: HTMLVideoElement;
}): Promise<NativeScannerSession> {
  const detector = new detectorClass({ formats: supportedFormats });
  const stream = await openCameraStream();
  videoElement.srcObject = stream;
  await videoElement.play();
  return {
    detector,
    stream,
  };
}

function loadZXingBrowser() {
  if (zxingBrowserModulePromise === null) {
    zxingBrowserModulePromise = import("@zxing/browser");
  }
  return zxingBrowserModulePromise;
}

function loadZXingLibrary() {
  if (zxingLibraryModulePromise === null) {
    zxingLibraryModulePromise = import("@zxing/library");
  }
  return zxingLibraryModulePromise;
}

export function describeScannerError(error: unknown) {
  if (error instanceof DOMException) {
    if (error.name === "AbortError") {
      return "Camera access was interrupted before Pantro could start scanning.";
    }
    if (error.name === "NotAllowedError") {
      return "Camera access was blocked. Allow camera permission or use manual/USB barcode entry instead.";
    }
    if (error.name === "NotFoundError") {
      return "No camera was found on this device.";
    }
    if (error.name === "NotReadableError") {
      return "The camera is already in use by another application or browser tab.";
    }
    if (error.name === "OverconstrainedError") {
      return "This camera could not satisfy Pantro's barcode scanning request.";
    }
    if (error.name === "SecurityError") {
      return "The browser blocked camera access for this page. Use HTTPS or manual/USB barcode entry instead.";
    }
  }

  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }

  return "Could not start the barcode scanner.";
}

export async function detectBarcodeScannerSupport(): Promise<BarcodeScannerSupport> {
  if (!window.isSecureContext) {
    return {
      preferredEngine: null,
      fallbackEngine: null,
      permissionState: "unknown",
      reason: "insecure_context",
      message: "Camera scanning needs HTTPS or localhost in a secure browser context.",
      nativeSupportedFormats: [],
      canRetry: false,
    };
  }

  if (!navigator.mediaDevices?.getUserMedia) {
    return {
      preferredEngine: null,
      fallbackEngine: null,
      permissionState: "unknown",
      reason: "media_devices_unavailable",
      message:
        "This browser cannot open the camera here. Use the barcode field or a USB scanner instead.",
      nativeSupportedFormats: [],
      canRetry: false,
    };
  }

  const permissionState = await queryCameraPermission();
  const nativeFormats = await getSupportedNativeFormats(getBarcodeDetector());
  const hasNativeSupport = nativeFormats.length > 0;

  if (permissionState === "denied") {
    return {
      preferredEngine: hasNativeSupport ? "native" : "zxing",
      fallbackEngine: hasNativeSupport ? "zxing" : null,
      permissionState,
      reason: "camera_permission_denied",
      message:
        "Camera permission is blocked for this site. Allow camera access in the browser, or keep using manual/USB barcode entry.",
      nativeSupportedFormats: nativeFormats,
      canRetry: true,
    };
  }

  if (hasNativeSupport) {
    return {
      preferredEngine: "native",
      fallbackEngine: "zxing",
      permissionState,
      reason: null,
      message: "Pantro can use the browser's built-in barcode scanner here.",
      nativeSupportedFormats: nativeFormats,
      canRetry: true,
    };
  }

  return {
    preferredEngine: "zxing",
    fallbackEngine: null,
    permissionState,
    reason: getBarcodeDetector() ? "native_formats_unavailable" : null,
    message:
      "Pantro will use its compatible camera scanner here. If the camera still cannot start, use manual/USB barcode entry instead.",
    nativeSupportedFormats: nativeFormats,
    canRetry: true,
  };
}

export async function startBarcodeScanner({
  support,
  videoElement,
  onDetected,
  onStatus,
}: StartBarcodeScannerOptions): Promise<ActiveBarcodeScannerSession> {
  if (!support.preferredEngine) {
    throw new Error(support.message);
  }

  if (support.permissionState === "denied") {
    throw new Error(support.message);
  }

  if (support.preferredEngine === "native") {
    const detectorClass = getBarcodeDetector();
    if (!detectorClass || support.nativeSupportedFormats.length === 0) {
      if (support.fallbackEngine === "zxing") {
        onStatus?.("Starting Pantro's compatible camera scanner…");
        return startBarcodeScanner({
          support: {
            ...support,
            preferredEngine: "zxing",
            fallbackEngine: null,
          },
          videoElement,
          onDetected,
          onStatus,
        });
      }
      throw new Error("This browser does not expose barcode formats Pantro can read.");
    }

    try {
      onStatus?.("Requesting camera permission…");
      const nativeScanner = await startNativeBarcodeScanner({
        detectorClass,
        supportedFormats: support.nativeSupportedFormats,
        videoElement,
      });

      let cancelled = false;
      let frameRequestId: number | null = null;
      let detecting = false;

      const stop = () => {
        cancelled = true;
        if (frameRequestId !== null) {
          window.cancelAnimationFrame(frameRequestId);
          frameRequestId = null;
        }
        nativeScanner.stream.getTracks().forEach((track) => track.stop());
        clearVideoElement(videoElement);
      };

      const detectFrame = async () => {
        if (cancelled) {
          return;
        }
        if (detecting) {
          frameRequestId = window.requestAnimationFrame(() => {
            void detectFrame();
          });
          return;
        }
        if (videoElement.readyState < HTMLMediaElement.HAVE_ENOUGH_DATA) {
          frameRequestId = window.requestAnimationFrame(() => {
            void detectFrame();
          });
          return;
        }

        detecting = true;
        try {
          const results = await nativeScanner.detector.detect(videoElement);
          const barcode = results
            .map((result) => normalizeBarcodeValue(result.rawValue ?? ""))
            .find(Boolean);
          if (barcode) {
            onDetected(barcode);
          }
        } finally {
          detecting = false;
        }

        frameRequestId = window.requestAnimationFrame(() => {
          void detectFrame();
        });
      };

      onStatus?.("Point the camera at the barcode.");
      frameRequestId = window.requestAnimationFrame(() => {
        void detectFrame();
      });

      return {
        engine: "native",
        stop,
      };
    } catch (error) {
      if (support.fallbackEngine === "zxing") {
        onStatus?.("Built-in scanning was unavailable. Starting Pantro's compatible scanner…");
        return startBarcodeScanner({
          support: {
            ...support,
            preferredEngine: "zxing",
            fallbackEngine: null,
          },
          videoElement,
          onDetected,
          onStatus,
        });
      }
      throw error;
    }
  }

  onStatus?.("Starting Pantro's compatible camera scanner…");
  const [zxingBrowser, zxingLibrary] = await Promise.all([loadZXingBrowser(), loadZXingLibrary()]);
  const {
    BarcodeFormat,
    ChecksumException,
    DecodeHintType,
    FormatException,
    NotFoundException,
  } = zxingLibrary;
  const hints = new Map();
  hints.set(DecodeHintType.POSSIBLE_FORMATS, [
    BarcodeFormat.EAN_13,
    BarcodeFormat.EAN_8,
    BarcodeFormat.UPC_A,
    BarcodeFormat.UPC_E,
    BarcodeFormat.CODE_128,
  ]);

  const reader = new zxingBrowser.BrowserMultiFormatReader(hints, {
    delayBetweenScanAttempts: 180,
    delayBetweenScanSuccess: 900,
    tryPlayVideoTimeout: 5000,
  });

  const controls = await reader.decodeFromConstraints(
    {
      audio: false,
      video: getPreferredCameraConstraints(),
    },
    videoElement,
    (result, error) => {
      if (result) {
        const barcode = normalizeBarcodeValue(result.getText());
        if (barcode) {
          onDetected(barcode);
        }
        return;
      }

      if (
        !error ||
        error instanceof NotFoundException ||
        error instanceof ChecksumException ||
        error instanceof FormatException
      ) {
        return;
      }

      throw error;
    },
  ).catch(async (error) => {
    if (!shouldRetryWithDefaultCamera(error)) {
      throw error;
    }

    onStatus?.("Starting the default camera instead…");
    return reader.decodeFromConstraints(
      {
        audio: false,
        video: true,
      },
      videoElement,
      (result, decodeError) => {
        if (result) {
          const barcode = normalizeBarcodeValue(result.getText());
          if (barcode) {
            onDetected(barcode);
          }
          return;
        }

        if (
          !decodeError ||
          decodeError instanceof NotFoundException ||
          decodeError instanceof ChecksumException ||
          decodeError instanceof FormatException
        ) {
          return;
        }

        throw decodeError;
      },
    );
  });

  onStatus?.("Point the camera at the barcode.");

  return createZXingSession({
    controls,
    videoElement,
  });
}

function createZXingSession({
  controls,
  videoElement,
}: {
  controls: IScannerControls;
  videoElement: HTMLVideoElement;
}): ActiveBarcodeScannerSession {
  return {
    engine: "zxing",
    stop: () => {
      controls.stop();
      clearVideoElement(videoElement);
    },
  };
}
