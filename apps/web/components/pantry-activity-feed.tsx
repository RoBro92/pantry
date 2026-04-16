"use client";

import { useMemo, useState } from "react";
import type { PantryAuditEventSummary } from "../lib/api-types";
import { ModalShell } from "./modal-shell";

type PantryActivityFeedProps = {
  events: PantryAuditEventSummary[];
};

type ActivityFilter = "24h" | "1w" | "all";

function formatTimestamp(value: string) {
  return new Date(value).toLocaleString("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function isEventVisible(event: PantryAuditEventSummary, filter: ActivityFilter) {
  if (filter === "all") {
    return true;
  }

  const now = Date.now();
  const occurredAt = new Date(event.occurred_at).getTime();
  const maxAgeMs = filter === "24h" ? 24 * 60 * 60 * 1000 : 7 * 24 * 60 * 60 * 1000;
  return now - occurredAt <= maxAgeMs;
}

export function PantryActivityFeed({ events }: PantryActivityFeedProps) {
  const [filter, setFilter] = useState<ActivityFilter>("24h");
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);

  const filteredEvents = useMemo(
    () => events.filter((event) => isEventVisible(event, filter)),
    [events, filter],
  );

  if (events.length === 0) {
    return <p>No pantry activity has been recorded yet.</p>;
  }

  const visibleEvents = filteredEvents.slice(0, 5);
  const hasMore = filteredEvents.length > visibleEvents.length;

  return (
    <>
      <div className="activity-toolbar">
        <div className="view-toggle" role="tablist" aria-label="Recent activity time range">
          <button
            type="button"
            className={filter === "24h" ? "primary-button compact-button" : "ghost-button compact-button"}
            onClick={() => setFilter("24h")}
          >
            24h
          </button>
          <button
            type="button"
            className={filter === "1w" ? "primary-button compact-button" : "ghost-button compact-button"}
            onClick={() => setFilter("1w")}
          >
            1 week
          </button>
          <button
            type="button"
            className={filter === "all" ? "primary-button compact-button" : "ghost-button compact-button"}
            onClick={() => setFilter("all")}
          >
            All
          </button>
        </div>
        <span className="pill">{filteredEvents.length} entries</span>
      </div>

      {filteredEvents.length === 0 ? (
        <div className="empty-state">
          <p>No activity matched this time range.</p>
        </div>
      ) : (
        <>
          <ol className="activity-feed activity-feed-compact">
            {visibleEvents.map((event) => (
              <li key={event.external_id} className="activity-feed-item">
                <div className="activity-feed-time">
                  <time dateTime={event.occurred_at}>{formatTimestamp(event.occurred_at)}</time>
                </div>
                <div className="activity-feed-copy">
                  <strong>{event.summary}</strong>
                  <span>
                    {event.actor_display ?? "System"} · {event.action.replaceAll(".", " / ")}
                  </span>
                </div>
              </li>
            ))}
          </ol>
          {hasMore ? (
            <button
              type="button"
              className="ghost-button compact-button"
              onClick={() => setIsHistoryOpen(true)}
            >
              View history
            </button>
          ) : null}
        </>
      )}

      {isHistoryOpen ? (
        <ModalShell
          title="Pantro activity history"
          description="Review the recent pantry log in a denser scrollable view."
          onClose={() => setIsHistoryOpen(false)}
          panelClassName="modal-panel modal-panel-wide"
        >
          <div className="activity-history-scroll">
            <ol className="activity-feed">
              {filteredEvents.map((event) => (
                <li key={event.external_id} className="activity-feed-item">
                  <div className="activity-feed-time">
                    <time dateTime={event.occurred_at}>{formatTimestamp(event.occurred_at)}</time>
                  </div>
                  <div className="activity-feed-copy">
                    <strong>{event.summary}</strong>
                    <span>
                      {event.actor_display ?? "System"} · {event.action.replaceAll(".", " / ")}
                    </span>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </ModalShell>
      ) : null}
    </>
  );
}
