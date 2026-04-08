"use client";

import type { ReactNode } from "react";

type ModalShellProps = {
  title: string;
  description?: string;
  onClose: () => void;
  closeOnBackdropClick?: boolean;
  children: ReactNode;
};

export function ModalShell({
  title,
  description,
  onClose,
  closeOnBackdropClick = true,
  children,
}: ModalShellProps) {
  return (
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
        className="modal-panel"
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
          <button type="button" className="ghost-button modal-close-button" onClick={onClose}>
            Close
          </button>
        </div>
        {children}
      </section>
    </div>
  );
}
