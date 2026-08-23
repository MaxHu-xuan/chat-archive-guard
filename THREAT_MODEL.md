# Threat model

## Assets

- Chat text and attachments represented in local archives.
- Authentication material and personal data embedded in records.
- SQLite databases, including committed transactions that remain in WAL.
- Absolute filesystem layout and exception details.

## Security goals

1. Do not transmit archive data.
2. Do not modify source files or source databases.
3. Do not emit detected values, record bodies, SQL values, absolute paths, or
   raw exception strings.
4. Detect common secret/PII patterns across supported text and SQLite values.
5. Surface malformed records, SQLite integrity failures, and broad file modes.
6. Bound memory and row consumption.

## Trust assumptions

- The operating system, Python interpreter, and standard-library SQLite build
  are trusted.
- The caller controls the scan root and can read it legitimately.
- A hostile process may attempt to swap or change SQLite files while they are
  copied; identity and content stability checks are expected to fail closed.
- SQLite loadable extensions are not enabled.

## Controls

- No networking or telemetry code is present.
- The release-tree audit rejects direct imports of common networking,
  telemetry, remote-service, and process-launch modules and includes synthetic
  detector self-tests.
- Traversal rejects symlinks in the scan-root ancestry and skips symlinks below
  it; regular files use `O_NOFOLLOW` where the platform provides it.
- SQLite never opens a source database or source WAL/SHM. Where `O_NOFOLLOW`
  exists, each present part is copied through a no-follow descriptor into a
  private mode-`0700` directory, source identity and SHA-256 are rechecked, and
  only the mode-`0600` copy is opened with URI `mode=ro` and backed up to
  memory. Without that primitive, SQLite fails closed as
  `sqlite.sidecar_unsafe` rather than weakening the snapshot boundary.
- Reports use a closed schema of relative path, category, and integer count.
- All caught scan errors map to fixed categories; exception messages are
  discarded.
- File, retained-finding, text/SQLite byte, SQLite row, and SQLite value limits
  are configurable within finite hard maxima enforced by `ScanConfig` for both
  library and CLI callers. Reaching any aggregate limit is explicit, marks the
  report incomplete and truncated, and prevents health.

## Out of scope and residual risks

- General non-SQLite files being changed by a hostile process during scanning.
- A filesystem or privileged adversary able to defeat descriptor, inode,
  timestamp, and repeated-content checks.
- Windows ACL interpretation. POSIX broad-mode findings are emitted only where
  POSIX mode semantics are available.
- Encrypted, compressed, proprietary, or remote database formats.
- Exhaustive DLP, semantic re-identification, malware analysis, and OCR.
- PII hidden by encoding, fragmentation, encryption, or unsupported formats.
- Contents of unsupported regular-file formats. Such files remain visible in
  `files_seen` and receive the file-mode check, but do not enter
  `files_scanned` and do not alone make a report incomplete.
- Filename confidentiality: relative paths are deliberately included.
- SQLite virtual tables may be unavailable in the local SQLite build; this is
  reported only as a generic table-scan category.
- Static publication checks cannot prove the absence of dynamically
  constructed networking, telemetry, or every sensitive-data shape; final
  source and provenance review remains required.
