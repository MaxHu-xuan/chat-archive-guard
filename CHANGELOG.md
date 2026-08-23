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
- Bilingual use-case, machine-readable-result, architecture, and FAQ guidance
  for accurate search and AI discovery without expanding claimed capabilities.
- Package discovery metadata for chat exports, offline scanning, secret
  scanning, PII detection, JSONL, SQLite WAL, and read-only operation.
- User-first Chinese and English guidance for archive integrity, privacy audits,
  rotated-log handling, and the limits around message completeness and source
  attribution.
- Aggregate-only `--summary-only` JSON and text reports that preserve status,
  coverage, finding totals, and categories while omitting finding rows and
  relative filenames.
- A cross-platform canonical source-archive builder with portable path checks,
  fixed metadata, content verification, and reproducibility self-tests.

### Security

- SQLite inspection requires an atomic no-follow open and otherwise fails
  closed as `sqlite.sidecar_unsafe`.
- Reports contain relative paths, categories, and counts, never matched values
  or absolute source paths.
- Failures that leave eligible content unverified mark the report incomplete
  and truncated instead of overstating scan coverage.
- Release builds remove local account metadata from source archives and use a
  public fixed timestamp for wheel members.
