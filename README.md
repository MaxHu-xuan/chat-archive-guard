# ChatArchiveGuard（聊天归档守护）

ChatArchiveGuard is a local, read-only diagnostic CLI for text, JSON, JSONL,
and SQLite chat archives. It detects common secret and personal-data patterns,
malformed records, SQLite integrity failures, and overly broad POSIX file
modes.

中文简介：在本地只读扫描聊天归档，检查秘密信息、个人数据、格式错误、SQLite 完整性和文件权限；报告只返回相对路径、类别与数量，不回显聊天内容。

Its output contract is intentionally narrow: reports contain only a path
relative to the scan root, a category, and a count. Matching text, JSON values,
SQL values, exception messages, and absolute paths are never included.

ChatArchiveGuard is licensed under the Apache License, Version 2.0. See
`LICENSE`. Provenance and data-boundary details are documented in
`PROVENANCE.md`.

## Privacy properties

- Local-only operation with no network client, telemetry, analytics, or update
  check.
- Where the operating system provides `O_NOFOLLOW` (including supported Linux
  and macOS runners), source SQLite, WAL, and SHM files are copied into a
  mode-`0700` temporary directory with mode-`0600` files. SQLite opens only
  that private copy, then backs it into memory for inspection.
- If atomic no-follow opens are unavailable, as with standard-library Python
  on Windows, SQLite inspection fails closed as `sqlite.sidecar_unsafe` before
  SQLite opens any source or private database. Text, JSON, and JSONL scanning
  remains available.
- Source identity, size, and SHA-256 are checked again before SQLite opens the
  private copy. A concurrent change produces a finding instead of a partial
  green report.
- Counts-only findings; detected values are discarded immediately.
- Symlinks, including any symlink in the supplied root ancestry, are not
  followed.
- Safe defaults bound files and retained findings as well as bytes, SQLite rows,
  and inspected values. CLI overrides may lower these limits or raise them only
  within finite hard maxima.
- Tests create synthetic samples only at runtime and leave no fixtures behind.

Relative filenames are still metadata. Use neutral filenames if even archive
names are sensitive.

## Supported scope and limits

Content inspection covers `.txt`, `.md`, `.log`, `.csv`, `.tsv`, `.yaml`,
`.yml`, `.json`, `.jsonl`, and `.ndjson`, plus SQLite files identified by a
`.db`, `.sqlite`, or `.sqlite3` suffix or by the SQLite file header. SQLite WAL
and SHM sidecars are inspected only as part of their main database snapshot.

Other regular files count toward `files_seen` and, on POSIX, still receive the
file-mode check, but their contents are not inspected and they do not by
themselves make the report incomplete. Windows ACLs are not inferred from
POSIX mode bits and are not assessed. Compare `files_seen` with
`files_scanned`; use a different tool for compressed, encrypted, proprietary,
attachment, or other unsupported formats.

| CLI option | Default | Enforced maximum |
| --- | ---: | ---: |
| `--max-file-mib` | 16 MiB | 256 MiB |
| `--max-sqlite-rows` | 100,000 | 1,000,000 |
| `--max-sqlite-value-kib` | 1,024 KiB | 16,384 KiB |
| `--max-files` | 10,000 | 100,000 |
| `--max-findings` | 10,000 | 100,000 |

The byte limit applies per supported text file and to the combined main
database, WAL, and SHM snapshot for each SQLite database. Values must be
positive and cannot exceed these hard maxima.

## Install and run

Python 3.11 or newer is required. The runtime has no third-party dependencies.

```console
python -m pip install .
chat-archive-guard /path/to/archive
chat-archive-guard /path/to/archive --json
```

For an uninstalled checkout:

```console
PYTHONPATH=src python -m chat_archive_guard /path/to/archive --json
```

Exit status is `0` when no findings exist, `1` when findings exist, and `2`
when the scan root or limits are invalid.

## Finding categories

- `secret.*`: private-key markers, provider keys, bearer tokens, credential
  assignments, and JWT-shaped values.
- `pii.*`: email, selected phone formats, IPv4 addresses, national-ID-shaped
  values, and Luhn-valid payment-card-shaped values.
- `format.*`: malformed UTF-8, JSON, or JSONL.
- `sqlite.*`: open, schema, table-scan, or integrity-check failures.
- `permissions.group_or_other`: on POSIX, a regular file grants any
  group/other bits.
- `scan.*`: skipped symlinks, resource limits, or sanitized I/O errors.

When a file-count or finding-count limit stops traversal, or a byte, row, or
value limit leaves content uninspected, the limit is itself a finding. Reports
then set `complete=false`, `truncated=true`, and cannot be healthy, so a bounded
scan cannot report green merely because content remained uninspected.

Pattern matches are indicators, not proof. False positives and false negatives
are possible, so this tool complements rather than replaces data governance.

## Development checks

```console
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 python scripts/privacy_audit.py
PYTHONDONTWRITEBYTECODE=1 python scripts/privacy_audit.py --self-test
```

The hosted CI definition runs the full checks on Linux with Python 3.11-3.14
and adds Python 3.11 and 3.14 boundary jobs on macOS and Windows. On PowerShell, set
`$env:PYTHONDONTWRITEBYTECODE = "1"` and `$env:PYTHONPATH = "src"` before the
unit-test command rather than using POSIX inline environment assignments.

When auditing an unpacked source distribution, use the explicit sdist mode:

```console
PYTHONDONTWRITEBYTECODE=1 python scripts/privacy_audit.py --sdist /path/to/unpacked-sdist
PYTHONDONTWRITEBYTECODE=1 python scripts/privacy_audit.py --sdist --self-test /path/to/unpacked-sdist
```

`--sdist` permits only the standard
`src/chat_archive_guard.egg-info` directory and still scans every file inside
it. Any other `*.egg-info`, an additional or misplaced copy, or any other
generated directory remains a failure. Source-checkout mode permits no
`*.egg-info` directory.

The programmatic `self_test()` recognizes its own standard unpacked sdist from
matching package metadata and manifest evidence so the bundled unit tests can
run without changing their call signature. This recognition affects only the
self-test's initial audit; the default `audit()` and CLI audit remain strict
source-checkout mode unless `--sdist` is explicitly supplied.

The privacy audit validates required release metadata and the Apache-2.0 file,
and refuses common secret/PII literals, absolute host paths, network or process
imports, generated directories, symlinks, hardlinks, binary artifacts,
persistent test data, and oversized source files. It reports only relative
paths, categories, and counts. Its self-test uses runtime-only synthetic
canaries to verify those detectors without echoing the canary values.

This audit is a deterministic preflight, not proof that dynamically constructed
network access or every possible sensitive-data shape is absent. Review the
final source archive and its provenance before publication.

## Contributing and license

Contributions are accepted under Apache-2.0. Use synthetic test data only and
follow `CONTRIBUTING.md`; no DCO sign-off or personal information is required.
