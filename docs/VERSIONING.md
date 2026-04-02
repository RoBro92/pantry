# Versioning

## Source Of Truth

- The repository root `VERSION` file is the authoritative application version.

## Expected Usage

- Releases should update `VERSION`.
- Runtime services may read the version from environment variables derived from `VERSION`.
- Documentation and release notes should reference `VERSION`, not duplicate their own canonical version value.

## Version Shape

- Start at `0.1.0`.
- Use semantic-version-like increments.
- Tie database migrations and release notes to versioned changes once persistence begins.

