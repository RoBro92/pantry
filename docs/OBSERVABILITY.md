# Observability

## System Logs

- API and worker emit structured JSON logs.
- Request IDs should flow through API request handling.
- Worker runs should bind a run ID or correlation ID for background traces.

## Audit Events

- Audit events are domain records, not log lines.
- Use them for accountability on admin, membership, inventory, and other sensitive actions.
- Audit retention and query behavior should be designed separately from runtime logging sinks.

## Immediate Goals

- Keep logs machine-readable.
- Avoid leaking secrets.
- Make request and job correlation easy before the system becomes complex.

