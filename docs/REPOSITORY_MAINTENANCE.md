# Repository Maintenance

Public repository maintenance notes for Pantry.

## Recommended GitHub Settings

Configure these in the GitHub repository settings for `main`:

- Require a pull request before merging.
- Require status checks to pass before merging.
- Use these stable required checks: `API Tests`, `Web Checks`, and `Repo Sanity`.
- Optionally require branches to be up to date before merging.
- Restrict direct pushes to `main` unless there is an explicit emergency reason.
- Prefer squash merge for normal change sets so `main` stays readable.
- Keep release tagging and publishing separate from pull request validation.

## Release Workflow

- Pull requests validate normal changes through `Pull Request Validation`.
- Tagged releases publish through `Release Publish`.
- Create a release tag only from a reviewed and merged `main` commit.

## Public And Private Documentation

- Keep installation, contributor workflow, validation, architecture, and security guidance in the public repo.
- Keep scratchpads, tentative roadmap notes, internal planning, and other non-public working material under `private-docs/` or another private location.
- Do not merge private planning material into the public repository as contributor-facing documentation.
