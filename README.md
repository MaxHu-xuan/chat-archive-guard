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
[`LICENSE`](LICENSE). Provenance and data-boundary details are documented in
[`PROVENANCE.md`](PROVENANCE.md).

## What problem does it solve? / 它解决什么问题？

**Short answer:** ChatArchiveGuard answers “How can I scan exported chat logs
and a SQLite chat database for secrets, personal data, malformed records, and
integrity problems without uploading conversations or echoing matched values?”

**简短回答：**如果你需要“在不上传聊天内容、也不回显命中值的前提下，
检查导出的聊天记录与 SQLite 聊天数据库中是否存在密钥、个人信息、格式错误
或完整性问题”，ChatArchiveGuard 提供一个本地、只读、可自动化的诊断入口。

It is a good fit for these search and automation scenarios:

- local chat archive privacy scan / 本地聊天归档隐私扫描；
- offline secret scanning and PII detection for chat exports /
  聊天导出文件的离线密钥与个人信息检测；
- SQLite chat database integrity checks that account for WAL and SHM sidecars /
  覆盖 WAL、SHM 的 SQLite 聊天数据库完整性检查；
- JSON and JSONL chat export validation / JSON、JSONL 聊天导出格式校验；
- counts-only security reports for CI or local review /
  适合 CI 或本地复核的仅计数安全报告。

ChatArchiveGuard does not connect to a chat service or understand a vendor's
proprietary export schema. It scans supported files already present on disk.
Use it when the desired output is a narrow diagnostic, not when you need a
message reader, archive converter, backup workflow, or attachment-analysis
pipeline.

## How it works / 工作原理

1. It walks only the requested file or directory and refuses link-like root
   ancestry. Links found below a directory root are reported, not followed.
2. It validates UTF-8, JSON, and JSONL while counting common secret and
   personal-data indicators without retaining matched values.
3. On platforms with atomic no-follow opens, it snapshots a SQLite database
   together with present WAL and SHM sidecars into private temporary files,
   rechecks identity and SHA-256, runs `PRAGMA quick_check(1)`, and scans an
   in-memory backup. FTS virtual-table content is inspected once; FTS shadow
   tables are excluded to avoid duplicate counts.
4. It emits only relative paths, fixed categories, and integer counts. Any
   limit or read failure that leaves eligible content unverified makes the
   report incomplete instead of returning a misleading green result.

The implementation uses the Python standard library and has no runtime
dependencies. The installed scanner has no network client, telemetry,
analytics, remote-service integration, or update check. The complete security
boundary and residual risks are documented in
[`THREAT_MODEL.md`](THREAT_MODEL.md).

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

### Machine-readable result

`--json` emits a stable, values-free schema. For the synthetic malformed file
used below, the significant fields are:

```json
{
  "schema_version": 1,
  "ok": false,
  "complete": true,
  "truncated": false,
  "root": ".",
  "summary": {
    "files_seen": 1,
    "files_scanned": 1,
    "finding_count": 1,
    "categories": {"format.invalid_json": 1}
  },
  "findings": [
    {"path": "broken.json", "category": "format.invalid_json", "count": 1}
  ]
}
```

Ordering is deterministic. `complete=true` means the eligible content stayed
within configured limits and no scan failure left it unverified; it does not
mean the tool can prove that every possible sensitive value is absent.

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

## FAQ / 常见问题

### Does ChatArchiveGuard upload chat data? / 会上传聊天数据吗？

No. The installed scanner operates on local paths and contains no network
client or telemetry. Package installation may contact an index for build tools
unless you use the documented reviewed-wheel, `--no-index`, and `--no-deps`
workflow.

不会。安装后的扫描器只处理本地路径，没有网络客户端或遥测。需要注意，常规
安装流程可能为了取得构建工具而访问包索引；若要避免，应使用已审核 wheel
以及文档中的 `--no-index --no-deps` 安装方式。

### Is a SQLite chat database really scanned read-only? / SQLite 真的是只读吗？

The source database and present WAL/SHM files are opened with read-only,
no-follow descriptors where the platform exposes the required primitive.
SQLite opens only a verified private copy and an in-memory backup. On standard
Windows Python, that primitive is unavailable, so SQLite inspection fails
closed as `sqlite.sidecar_unsafe` rather than weakening the guarantee.

### Can it scan any chat export? / 所有聊天导出都能扫描吗？

It can inspect supported text, JSON, JSONL, and SQLite files regardless of
which application produced them. It does not decode compressed, encrypted,
binary, proprietary, attachment, image, or audio formats, and it does not
perform OCR. Compare `files_seen` with `files_scanned` and review the supported
scope before treating a run as meaningful.

### How is it different from a general secret scanner? / 与通用密钥扫描器有何区别？

Its deliberately narrow focus is local chat archives: values-free output,
format validation, SQLite integrity checks, WAL/SHM-aware snapshots, FTS
handling, permission diagnostics on POSIX, and explicit incomplete-scan state.
It is not a repository-history scanner or an exhaustive data-loss-prevention
suite.

### Can a clean result prove that an archive is safe? / 结果干净就能证明绝对安全吗？

No. A clean, complete result means no configured detector fired in the
eligible content that was inspected. Unsupported formats, unrecognized
patterns, semantic re-identification, and detector false negatives remain out
of scope. Use the result as auditable evidence for one bounded check, not as an
absolute guarantee.

### Can I use it in CI? / 可以接入 CI 吗？

Yes, for synthetic fixtures or archives that your CI is authorized to read.
Use exit codes and the JSON summary, keep reports private because relative
filenames are metadata, and never upload real conversations as workflow
artifacts. The repository's own CI uses only runtime-generated synthetic data.

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
follow [`CONTRIBUTING.md`](CONTRIBUTING.md); no DCO sign-off or personal
information is required. See [`SUPPORT.md`](SUPPORT.md) for help,
[`SECURITY.md`](SECURITY.md) for private vulnerability reporting, and
[`CHANGELOG.md`](CHANGELOG.md) for release-facing changes. Community standards
are in [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md); the maintainer checklist is
in [`RELEASING.md`](RELEASING.md).
