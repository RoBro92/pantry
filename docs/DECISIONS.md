# Decisions

## First-Run Setup Uses Persistent Staging

Pantry stores incomplete first-run configuration in a dedicated `setup_states` record instead of writing directly into live users, households, memberships, locations, or instance settings.

Reasoning:

- refreshes and in-wizard navigation need durable progress
- incomplete installs must not look initialized
- final completion should be transactional and explicit

Result:

- setup remains resumable until final confirmation
- secrets are staged safely
- live application tables are only populated during finalisation
