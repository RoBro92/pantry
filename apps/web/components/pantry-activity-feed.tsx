import type { PantryAuditEventSummary } from "../lib/api-types";

type PantryActivityFeedProps = {
  events: PantryAuditEventSummary[];
};

function formatTimestamp(value: string) {
  return new Date(value).toLocaleString("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function PantryActivityFeed({ events }: PantryActivityFeedProps) {
  if (events.length === 0) {
    return <p>No pantry activity has been recorded yet.</p>;
  }

  return (
    <ol className="activity-feed">
      {events.map((event) => (
        <li key={event.external_id} className="activity-feed-item">
          <div className="activity-feed-time">
            <time dateTime={event.occurred_at}>{formatTimestamp(event.occurred_at)}</time>
          </div>
          <div className="activity-feed-copy">
            <strong>{event.summary}</strong>
            <span>{event.actor_display ?? "System"} · {event.action.replaceAll(".", " / ")}</span>
          </div>
        </li>
      ))}
    </ol>
  );
}
