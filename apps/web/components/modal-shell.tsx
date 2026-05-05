"use client";

import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";

type ModalShellProps = {
  title: string;
  description?: string;
  onClose: () => void;
  closeOnBackdropClick?: boolean;
  showCloseButton?: boolean;
  panelClassName?: string;
  children: ReactNode;
};

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled]):not([type='hidden'])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
  "[contenteditable='true']",
].join(", ");
const AUTOFOCUS_SELECTOR = "[data-autofocus='true'], [autofocus]";

function isFocusableElement(element: HTMLElement) {
  if (element.hasAttribute("disabled") || element.getAttribute("aria-hidden") === "true") {
    return false;
  }

  return element.getClientRects().length > 0;
}

function getFocusableElements(container: HTMLElement | null) {
  if (!container) {
    return [];
  }

  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter(
    isFocusableElement,
  );
}

export function ModalShell({
  title,
  description,
  onClose,
  closeOnBackdropClick = true,
  showCloseButton = true,
  panelClassName,
  children,
}: ModalShellProps) {
  const panelRef = useRef<HTMLElement | null>(null);
  const contentRef = useRef<HTMLDivElement | null>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);
  const [portalTarget, setPortalTarget] = useState<HTMLElement | null>(null);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    if (typeof document === "undefined") {
      return;
    }

    setPortalTarget(document.body);
  }, []);

  useEffect(() => {
    if (typeof document === "undefined" || !portalTarget) {
      return;
    }

    returnFocusRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;

    const previousBodyOverflow = document.body.style.overflow;
    const previousHtmlOverflow = document.documentElement.style.overflow;

    document.body.style.overflow = "hidden";
    document.documentElement.style.overflow = "hidden";

    const frame = window.requestAnimationFrame(() => {
      const panelElement = panelRef.current;
      panelElement?.scrollTo({ top: 0, left: 0, behavior: "auto" });

      const activeElement =
        document.activeElement instanceof HTMLElement ? document.activeElement : null;
      if (panelElement && activeElement && panelElement.contains(activeElement)) {
        return;
      }

      const initialFocusTarget =
        contentRef.current?.querySelector<HTMLElement>(AUTOFOCUS_SELECTOR) ??
        getFocusableElements(contentRef.current)[0] ??
        getFocusableElements(panelElement)[0] ??
        panelElement;
      initialFocusTarget?.focus();
    });

    return () => {
      window.cancelAnimationFrame(frame);
      document.body.style.overflow = previousBodyOverflow;
      document.documentElement.style.overflow = previousHtmlOverflow;
      const returnFocusTarget = returnFocusRef.current;
      if (returnFocusTarget?.isConnected) {
        returnFocusTarget.focus();
      }
    };
  }, [portalTarget]);

  function handleFocusTrap(event: KeyboardEvent<HTMLElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      onClose();
      return;
    }

    if (event.key !== "Tab") {
      return;
    }

    if (!(event.target instanceof Node) || !event.currentTarget.contains(event.target)) {
      return;
    }

    const focusableElements = getFocusableElements(event.currentTarget);
    if (focusableElements.length === 0) {
      event.preventDefault();
      event.currentTarget.focus();
      return;
    }

    const firstFocusable = focusableElements[0];
    const lastFocusable = focusableElements[focusableElements.length - 1];
    const activeElement =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;

    if (!activeElement || !event.currentTarget.contains(activeElement)) {
      event.preventDefault();
      (event.shiftKey ? lastFocusable : firstFocusable).focus();
      return;
    }

    if (event.shiftKey) {
      if (activeElement === firstFocusable || activeElement === event.currentTarget) {
        event.preventDefault();
        lastFocusable.focus();
      }
      return;
    }

    if (activeElement === lastFocusable || activeElement === event.currentTarget) {
      event.preventDefault();
      firstFocusable.focus();
    }
  }

  if (!portalTarget) {
    return null;
  }

  return createPortal(
    <div
      className="modal-backdrop"
      role="presentation"
      onClick={(event) => {
        if (closeOnBackdropClick && event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <section
        ref={panelRef}
        className={panelClassName ?? "modal-panel"}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descriptionId : undefined}
        tabIndex={-1}
        onClick={(event) => event.stopPropagation()}
        onKeyDown={handleFocusTrap}
      >
        <div className="setup-card-toolbar">
          <div className="stack compact-stack">
            <h2 id={titleId}>{title}</h2>
            {description ? (
              <p id={descriptionId} className="section-copy">
                {description}
              </p>
            ) : null}
          </div>
          {showCloseButton ? (
            <button type="button" className="ghost-button modal-close-button" onClick={onClose}>
              Close
            </button>
          ) : null}
        </div>
        <div ref={contentRef}>{children}</div>
      </section>
    </div>,
    portalTarget,
  );
}
