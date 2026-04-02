# Observability

## System Logs

- API and worker emit structured JSON logs.
- Request IDs should flow through API request handling.
- Worker runs should bind a run ID or correlation ID for background traces.
- Import worker runs should bind the import job external ID and household external ID while processing queued jobs.
- Import lifecycle logs should make queued, claimed, completed, failed, and idle worker states easy to distinguish.
- AI request logs should bind the household external ID, provider config external ID, provider type, model, suggestion kind, and duration without leaking secrets.

## Audit Events

- Audit events are domain records, not log lines.
- Use them for accountability on admin, membership, inventory, and other sensitive actions.
- Reviewed import creation, review activity, confirmation, and failures should emit audit events.
- AI provider configuration saves and user-triggered AI suggestion requests should emit audit events.
- Audit retention and query behavior should be designed separately from runtime logging sinks.

## Immediate Goals

- Keep logs machine-readable.
- Avoid leaking secrets.
- Make request and job correlation easy before the system becomes complex.
- Make import processing failures observable without conflating runtime logs with household-visible audit history.
