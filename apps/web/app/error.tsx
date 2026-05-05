"use client";

import { useEffect } from "react";

type ErrorPageProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

export default function ErrorPage({ error, reset }: ErrorPageProps) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="page-shell">
      <section className="panel">
        <p className="eyebrow">Application Error</p>
        <h1>Something went wrong</h1>
        <p className="section-copy">
          The app hit an unexpected problem while loading this view.
        </p>
        <button type="button" className="primary-button" onClick={() => reset()}>
          Try again
        </button>
      </section>
    </main>
  );
}
