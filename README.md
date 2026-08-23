# ChatArchiveGuard（聊天归档守护）

- **English name:** ChatArchiveGuard
- **中文名：**聊天归档守护

**Positioning / 定位：** A local, read-only privacy and integrity diagnostic
for text, JSON, JSONL, and SQLite chat archives. / 面向文本、JSON、JSONL 与
SQLite 聊天归档的本地只读隐私与完整性诊断工具。

It detects common secret and personal-data patterns, malformed records, SQLite
integrity failures, and overly broad POSIX file modes. It is not a backup or
recovery tool, message viewer, attachment scanner, OCR system, or exhaustive
DLP product.

它检查常见秘密信息、个人数据、格式错误、SQLite 完整性和过宽的 POSIX
文件权限；它不负责备份恢复、消息浏览、附件扫描、OCR，也不承诺穷尽所有
敏感信息类型。

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
The project is not yet published to a package index; install it from a reviewed
source checkout.

The local-only guarantee applies to the installed scanner at runtime. Package
installers and PEP 517 build isolation may contact a configured package index
to obtain build tools. To install a previously reviewed wheel without index
access or dependency resolution, use:

```console
python -m pip install --no-index --no-deps /path/to/chat_archive_guard-0.1.0-py3-none-any.whl
```

```console
python -m pip install .
chat-archive-guard /path/to/archive
chat-archive-guard /path/to/archive --json
```

For an uninstalled checkout:

```console
PYTHONPATH=src python -m chat_archive_guard /path/to/archive --json
```

PowerShell uses a separate environment-variable syntax:

```powershell
$env:PYTHONPATH = "src"
python -m chat_archive_guard C:\path\to\archive --json
```

Exit status is `0` when no findings exist, `1` when findings exist, and `2`
when the scan root or limits are invalid.

### Verify the installation with synthetic input

On Linux or macOS:

```sh
demo_dir="$(mktemp -d)"
demo_dir="$(cd "$demo_dir" && pwd -P)"
printf '%s\n' '{invalid' > "$demo_dir/broken.json"
chmod 600 "$demo_dir/broken.json"
chat-archive-guard "$demo_dir" --json
rm -r "$demo_dir"
```

On Windows PowerShell:

```powershell
$demo = Join-Path ([System.IO.Path]::GetTempPath()) ("chat-archive-guard-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $demo | Out-Null
Set-Content -Path (Join-Path $demo "broken.json") -Value "{invalid" -Encoding utf8
chat-archive-guard $demo --json
Remove-Item -LiteralPath $demo -Recurse
```

The deliberately malformed synthetic file must produce exit status `1`, an
`ok=false` report, and one `format.invalid_json` finding. The report must not
contain the absolute temporary path or the invalid input value.

### Platform behavior

| Capability | Linux | macOS | Windows |
| --- | --- | --- | --- |
| Text, JSON, and JSONL inspection | Supported | Supported | Supported |
| SQLite, WAL, and SHM inspection | Supported when `O_NOFOLLOW` is exposed | Supported when `O_NOFOLLOW` is exposed | Fails closed as `sqlite.sidecar_unsafe` with standard-library Python |
| Permission diagnostic | POSIX group/other mode bits | POSIX group/other mode bits | ACLs are not inferred or audited |
| Link defense | Symlinks rejected or skipped | Symlinks rejected or skipped | Reparse points and junction-like entries rejected or skipped |

Windows is a supported platform, but its standard-library Python does not
provide the atomic no-follow primitive required by this threat model for
SQLite sidecars. The scanner therefore reports that SQLite input as unsafe
instead of silently opening it. Such a database is not counted in
`files_scanned`; the report sets `complete=false` and `truncated=true`. Do not
treat `chmod` output on Windows as an ACL security assessment.

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
Metadata/read failures and SQLite snapshot, open, integrity, schema, or table
scan failures that leave content unverified use the same incomplete/truncated
state alongside their fixed finding category. `files_scanned` counts supported
files whose content scan reached its inspection phase, not files merely seen.

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
See `SUPPORT.md` for help, `SECURITY.md` for private vulnerability reporting,
and `CHANGELOG.md` for release-facing changes. Community standards are in
`CODE_OF_CONDUCT.md`; the maintainer checklist is in `RELEASING.md`.
