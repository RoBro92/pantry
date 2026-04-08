# AGENTS

Pantry uses a branch and pull request workflow.

- Do not work directly on `main` for normal feature, fix, or docs changes.
- Create a short-lived branch from `main` and keep each change scoped and reviewable.
- Run the relevant local validation before considering the work complete.
- Open a pull request, review the diff and checks, then merge back to `main`.
- Update public documentation when public behavior, setup, validation, or contributor workflow changes.
- Keep internal planning notes, scratchpads, and other private material out of the public repo. Store that material under `private-docs/` or another private location instead.
- Use Codex or other automation as an assistant, not as a substitute for reviewing the final diff, generated files, workflow changes, and test results.
