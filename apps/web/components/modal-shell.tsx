"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
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
  const [portalTarget, setPortalTarget] = useState<HTMLElement | null>(null);

  useEffect(() => {
    if (typeof document === "undefined") {
      return;
    }

    setPortalTarget(document.body);
  }, []);

  useEffect(() => {
    if (typeof document === "undefined") {
      return;
    }

    const previousBodyOverflow = document.body.style.overflow;
    const previousHtmlOverflow = document.documentElement.style.overflow;

    document.body.style.overflow = "hidden";
    document.documentElement.style.overflow = "hidden";

    const frame = window.requestAnimationFrame(() => {
      panelRef.current?.scrollTo({ top: 0, left: 0, behavior: "auto" });
    });

    return () => {
      window.cancelAnimationFrame(frame);
      document.body.style.overflow = previousBodyOverflow;
      document.documentElement.style.overflow = previousHtmlOverflow;
    };
  }, []);

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
        aria-label={title}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="setup-card-toolbar">
          <div className="stack compact-stack">
            <h2>{title}</h2>
            {description ? <p className="section-copy">{description}</p> : null}
          </div>
          {showCloseButton ? (
            <button type="button" className="ghost-button modal-close-button" onClick={onClose}>
              Close
            </button>
          ) : null}
        </div>
        {children}
      </section>
    </div>,
    portalTarget,
  );
}
