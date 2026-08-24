# Changelog

All notable changes to ChatArchiveGuard（聊天归档守护）will be recorded here.
The project follows Semantic Versioning after its first public release.

## Unreleased

Release status: this remains an unreleased 0.1.0 candidate. No release date is
recorded until the final tag and artifacts are approved.

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
- A deterministic runtime-only JSONL and SQLite demo generator with visibly
  invalid canaries, stable aggregate findings, and no committed data fixtures.
- Separate macOS/Linux and Windows commands, observed demo output, a concise
  three-project chooser, and draft 0.1.0 release notes.

### Security

- Build the synthetic SQLite demo in a private temporary file, close it, then
  publish with exclusive final-file creation so a racing existing database is
  never opened, read, or modified.
- Preserve source-swap detection on Windows without comparing incompatible
  path-stat and open-handle timestamp fields.
- SQLite inspection requires an atomic no-follow open and otherwise fails
  closed as `sqlite.sidecar_unsafe`.
- Reports contain relative paths, categories, and counts, never matched values
  or absolute source paths.
- Failures that leave eligible content unverified mark the report incomplete
  and truncated instead of overstating scan coverage.
- Release builds remove local account metadata from source archives and use a
  public fixed timestamp for wheel members.
