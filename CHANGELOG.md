# Changelog

All notable changes to ChatArchiveGuard（聊天归档守护）will be recorded here.
The project follows Semantic Versioning after its first public release.

## Unreleased

### Added

- Initial public-preview documentation and package metadata.
- Local, values-free diagnostics for supported text, JSON, JSONL, and SQLite
  archives.
- Explicit Linux, macOS, and Windows behavior and security boundaries.
- Synthetic tests, publication privacy audit, and cross-platform CI.

### Security

- SQLite inspection requires an atomic no-follow open and otherwise fails
  closed as `sqlite.sidecar_unsafe`.
- Reports contain relative paths, categories, and counts, never matched values
  or absolute source paths.
- Failures that leave eligible content unverified mark the report incomplete
  and truncated instead of overstating scan coverage.
