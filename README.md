# ChatArchiveGuard（聊天归档守护）

[中文说明](#中文说明) | [English overview](#english-overview) |
[技术参考](#中文技术参考) | [Technical reference](#english-technical-reference)

## 中文说明

ChatArchiveGuard（聊天归档守护）帮助个人和团队在自己的电脑上检查聊天
归档。它适合在保存、迁移、共享或进一步处理聊天导出文件之前，先做一次
本地、只读的隐私与完整性检查。

扫描结果只包含相对文件路径、检查类别和数量，不会输出命中的聊天正文、
JSON 值、SQL 值、异常原文或绝对路径。扫描器没有网络客户端、遥测或自动
更新功能。

### 它解决什么问题

你可以用它完成本地聊天归档隐私扫描、离线密钥扫描、个人信息检测、
JSON/JSONL 聊天导出校验，以及 SQLite 聊天数据库完整性检查。它会检查：

- 常见密钥、令牌、凭证和私钥标记；
- 邮箱、部分电话号码、IPv4 地址、证件号形态和通过 Luhn 校验的银行卡号形态；
- 无效 UTF-8、JSON 和 JSONL；
- SQLite 数据库完整性及可读取的文本值；
- POSIX 系统上过宽的文件权限；
- 符号链接、读取失败和超过资源上限的未完整扫描。

它不会连接聊天平台，也不会解析某个平台的专有导出包。它不是聊天阅读器、
备份恢复工具、附件扫描器、OCR 工具或完整的数据防泄漏系统。

### 三步使用

1. 在已经审核过的源码目录中安装：

   ```console
   python -m pip install .
   ```

2. 扫描一个文件或目录。需要程序处理结果时增加 `--json`：

   ```console
   chat-archive-guard /path/to/archive
   chat-archive-guard /path/to/archive --json
   ```

3. 查看退出码和结果中的 `ok`、`complete`、`truncated`。只有在没有发现项、
   扫描完整且未截断时，`ok` 才会是 `true`。

### 看懂结果

| 内容 | 含义 |
| --- | --- |
| 退出码 `0` | 没有发现项，并且扫描完整 |
| 退出码 `1` | 发现问题，或有内容未能完整检查 |
| 退出码 `2` | 扫描路径或参数无效 |
| `files_seen` | 遍历到的常规文件数量 |
| `files_scanned` | 已进入受支持内容检查阶段的文件数量 |
| `complete` | 符合范围的内容是否全部完成检查 |
| `truncated` | 是否因限制或错误留下未检查内容 |
| `findings` | 相对路径、固定类别和数量，不含命中值 |

下面是一个合成的无效 JSON 文件所产生的完整结果。`format.invalid_json`
表示 JSON 格式错误：

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

`complete=true` 只表示本次符合范围的内容完成了检查，不代表工具能证明文件中
不存在任何可能的敏感信息。

### 安装与平台差异

需要 Python 3.11 或更高版本。运行时没有第三方依赖。目前项目尚未发布到包
索引，请从已审核的源码或 wheel 安装。

常规安装和 PEP 517 构建隔离可能访问已配置的包索引以取得构建工具。若已经
拿到审核过的 wheel，可使用下面的命令避免索引访问和依赖解析：

```console
python -m pip install --no-index --no-deps /path/to/chat_archive_guard-0.1.0-py3-none-any.whl
```

未安装时，macOS 和 Linux 可以从源码目录运行：

```console
PYTHONPATH=src python -m chat_archive_guard /path/to/archive --json
```

Windows PowerShell 使用不同的环境变量语法：

```powershell
$env:PYTHONPATH = "src"
python -m chat_archive_guard C:\path\to\archive --json
```

| 能力 | Linux | macOS | Windows |
| --- | --- | --- | --- |
| 文本、JSON、JSONL 检查 | 支持 | 支持 | 支持 |
| SQLite、WAL、SHM 检查 | 提供 `O_NOFOLLOW` 时支持 | 提供 `O_NOFOLLOW` 时支持 | 标准 Python 下安全拒绝 |
| 文件权限检查 | POSIX 权限位 | POSIX 权限位 | 不推断或审计 ACL |
| 链接防护 | 拒绝或跳过符号链接 | 拒绝或跳过符号链接 | 拒绝或跳过重解析点及类似入口 |

Windows 标准库 Python 没有本项目安全边界要求的原子 no-follow 打开能力。
遇到 SQLite 时，工具会返回 `sqlite.sidecar_unsafe`，并设置
`complete=false`、`truncated=true`，而不是降低保护等级后继续读取。

### 使用范围与限制

工具会检查 `.txt`、`.md`、`.log`、`.csv`、`.tsv`、`.yaml`、`.yml`、
`.json`、`.jsonl` 和 `.ndjson` 的文本内容。`.db`、`.sqlite`、`.sqlite3`
以及带 SQLite 文件头的文件会按 SQLite 处理；WAL 和 SHM 只会随主数据库一起
处理。

压缩包、加密文件、专有格式、附件、图片、音频和其他二进制文件的内容不在
检查范围内。它们仍计入 `files_seen`，并在 POSIX 系统上接受权限检查，但不
计入 `files_scanned`。请比较这两个字段，不要仅凭 `ok` 之外的单一数字判断
归档是否已充分检查。

文件名本身也是元数据。即使报告不输出命中内容，分享报告前仍应检查其中的
相对文件名是否敏感。匹配结果只是风险提示，可能存在误报和漏报。

### 常见问题

#### 会上传聊天数据吗？

不会。安装后的扫描器只读取本地路径，没有网络客户端或遥测。安装过程可能
访问包索引；需要完全离线时，请使用已审核 wheel 和前述 `--no-index --no-deps`
命令。

#### 能检查所有聊天导出吗？

不能。只要文件属于支持的文本、JSON、JSONL 或 SQLite 范围，就不要求它来自
特定应用；压缩、加密、专有格式和附件内容不受支持。

#### 结果没有发现项就代表绝对安全吗？

不代表。完整且无发现的结果只说明已检查内容没有触发当前检测规则。未知模式、
不支持的格式、语义重识别和检测器漏报仍然可能存在。

#### 可以在 CI 中使用吗？

可以，但 CI 必须有权读取输入。建议通过退出码和 JSON 摘要判断结果，不要把
真实聊天内容或带敏感文件名的报告上传为公开构建产物。本项目自己的 CI 只使用
运行时生成的合成数据。

## 中文技术参考

### 工作原理

1. 工具只遍历指定文件或目录。扫描根路径的链接型入口会被拒绝，目录中的链接
   会被报告但不会跟随。
2. 文本检测器只累计类别数量，不保留命中值。JSON 和 JSONL 会同时接受格式
   校验。
3. 在支持原子 no-follow 打开的系统上，SQLite 主文件和现有 WAL、SHM 会复制
   到权限为 `0700` 的临时目录和权限为 `0600` 的临时文件。工具重新校验来源
   身份和 SHA-256，只让 SQLite 打开私有副本，并在内存备份上运行
   `PRAGMA quick_check(1)` 和内容检查。
4. FTS 虚拟表内容只检查一次，FTS 影子表不会重复计数。来源发生并发变化、读取
   失败或达到限制时，结果会明确标为不完整。

扫描器只使用 Python 标准库。更完整的威胁模型和残余风险见
[`THREAT_MODEL.md`](THREAT_MODEL.md)。

### 检查类别

- `secret.*`：私钥标记、提供商密钥、Bearer 令牌、凭证赋值和 JWT 形态值；
- `pii.*`：邮箱、部分电话、IPv4、证件号形态和通过 Luhn 校验的银行卡号形态；
- `format.*`：无效 UTF-8、JSON 或 JSONL；
- `sqlite.*`：快检、打开、结构或表扫描失败；
- `permissions.group_or_other`：POSIX 文件向组或其他用户授予了权限；
- `scan.*`：链接、读取错误或资源限制。

### 资源限制

| 参数 | 默认值 | 最大值 |
| --- | ---: | ---: |
| `--max-file-mib` | 16 MiB | 256 MiB |
| `--max-sqlite-rows` | 100,000 | 1,000,000 |
| `--max-sqlite-value-kib` | 1,024 KiB | 16,384 KiB |
| `--max-files` | 10,000 | 100,000 |
| `--max-findings` | 10,000 | 100,000 |

达到文件数、发现数、字节、行数或值大小限制时，结果会出现对应发现项，并设置
`complete=false`、`truncated=true`。有限扫描不会因为未检查内容暂时没有命中
而返回健康结果。

## English overview

ChatArchiveGuard checks exported chat archives on your own computer. Individuals
and teams can run it before storing, migrating, sharing, or further processing
chat exports. The scan is local and read-only.

Reports contain only relative file paths, fixed categories, and counts. They do
not contain matched chat text, JSON values, SQL values, raw exception messages,
or absolute paths. The scanner has no network client, telemetry, or automatic
update check.

### What problem does it solve?

ChatArchiveGuard provides a local chat archive privacy scan, offline secret
scanning and PII detection, JSON/JSONL chat export validation, and SQLite chat
database integrity checks. It checks for:

- common keys, tokens, credential assignments, and private-key markers;
- email addresses, selected phone formats, IPv4 addresses, national-ID-shaped
  values, and Luhn-valid payment-card-shaped values;
- malformed UTF-8, JSON, and JSONL;
- SQLite integrity problems and readable text values;
- broad file permissions on POSIX systems;
- links, read failures, and resource limits that leave a scan incomplete.

It does not connect to a chat service or parse a vendor-specific export bundle.
It is not a message viewer, backup or recovery tool, attachment scanner, OCR
system, or exhaustive data-loss-prevention product.

### Three steps

1. Install from a reviewed source checkout:

   ```console
   python -m pip install .
   ```

2. Scan one file or directory. Add `--json` for machine-readable output:

   ```console
   chat-archive-guard /path/to/archive
   chat-archive-guard /path/to/archive --json
   ```

3. Read the exit status and the `ok`, `complete`, and `truncated` fields. `ok`
   is true only when there are no findings and the scan is complete and not
   truncated.

### Read the result

| Item | Meaning |
| --- | --- |
| Exit `0` | No findings and the scan is complete |
| Exit `1` | Findings exist or some eligible content was not fully checked |
| Exit `2` | The scan path or limits are invalid |
| `files_seen` | Regular files encountered during traversal |
| `files_scanned` | Supported files that reached content inspection |
| `complete` | Whether all eligible content completed inspection |
| `truncated` | Whether a limit or error left content uninspected |
| `findings` | Relative paths, fixed categories, and counts only |

The JSON example in the Chinese section is language-independent and shows the
complete stable schema. Deterministic ordering makes it suitable for local
automation and authorized CI workflows.

### Install and run

Python 3.11 or newer is required. There are no third-party runtime dependencies.
The project is not yet published to a package index; install it from a reviewed
source checkout or wheel.

A normal install or PEP 517 build isolation may contact a configured package
index for build tools. Install a previously reviewed wheel without index access
or dependency resolution with:

```console
python -m pip install --no-index --no-deps /path/to/chat_archive_guard-0.1.0-py3-none-any.whl
```

Run an uninstalled checkout on macOS or Linux with:

```console
PYTHONPATH=src python -m chat_archive_guard /path/to/archive --json
```

PowerShell uses a different environment-variable syntax:

```powershell
$env:PYTHONPATH = "src"
python -m chat_archive_guard C:\path\to\archive --json
```

### Platform behavior

| Capability | Linux | macOS | Windows |
| --- | --- | --- | --- |
| Text, JSON, and JSONL inspection | Supported | Supported | Supported |
| SQLite, WAL, and SHM inspection | Supported when `O_NOFOLLOW` is exposed | Supported when `O_NOFOLLOW` is exposed | Fails closed with standard-library Python |
| Permission diagnostic | POSIX mode bits | POSIX mode bits | ACLs are not inferred or audited |
| Link defense | Symlinks rejected or skipped | Symlinks rejected or skipped | Reparse points and similar entries rejected or skipped |

Standard-library Python on Windows does not expose the atomic no-follow open
required by this threat model. SQLite input therefore produces
`sqlite.sidecar_unsafe`, `complete=false`, and `truncated=true` instead of being
opened under a weaker guarantee.

### Scope and limitations

Content inspection covers `.txt`, `.md`, `.log`, `.csv`, `.tsv`, `.yaml`,
`.yml`, `.json`, `.jsonl`, and `.ndjson`. Files ending in `.db`, `.sqlite`, or
`.sqlite3`, or carrying the SQLite header, are treated as databases. WAL and SHM
sidecars are handled only with their main database.

Compressed, encrypted, proprietary, attachment, image, audio, and other binary
content is unsupported. Those regular files still contribute to `files_seen`
and receive the POSIX permission check, but do not enter `files_scanned`.
Compare both fields before deciding whether the run covered what you intended.

Relative filenames are metadata and may still be sensitive. Pattern matches are
indicators rather than proof; false positives and false negatives are possible.

### FAQ

#### Does ChatArchiveGuard upload chat data?

No. The installed scanner reads local paths and contains no network client or
telemetry. Package installation may contact an index; use a reviewed wheel with
`--no-index --no-deps` when the installation must remain offline.

#### Can it scan every chat export?

No. It can inspect supported text, JSON, JSONL, and SQLite files regardless of
which application produced them. Compressed, encrypted, proprietary, and
attachment content is out of scope.

#### Does a clean result prove that an archive is safe?

No. A clean, complete result means no configured detector fired in the eligible
content that was inspected. Unsupported formats, unknown patterns, semantic
re-identification, and detector false negatives remain possible.

#### Can it run in CI?

Yes, when the CI system is authorized to read the input. Use exit codes and the
JSON summary, keep reports private when relative filenames are sensitive, and
never upload real conversations as public workflow artifacts. This project's CI
uses only synthetic data created at runtime.

## English technical reference

### How it works

1. Traversal stays within the requested file or directory. Link-like scan-root
   ancestry is rejected, and links below a directory root are reported rather
   than followed.
2. Text detectors accumulate category counts without retaining matched values.
   JSON and JSONL also receive format validation.
3. On systems with atomic no-follow opens, the SQLite database and present WAL
   and SHM sidecars are copied into a mode-`0700` temporary directory with
   mode-`0600` files. Source identity and SHA-256 are checked again, SQLite opens
   only the private copy, and `PRAGMA quick_check(1)` plus content inspection run
   on an in-memory backup.
4. FTS virtual-table content is scanned once while FTS shadow tables are excluded
   from duplicate counting. Concurrent source changes, read failures, and limits
   explicitly make the report incomplete.

The scanner uses only the Python standard library. See
[`THREAT_MODEL.md`](THREAT_MODEL.md) for the full boundary and residual risks.

### Finding categories

- `secret.*`: private-key markers, provider keys, bearer tokens, credential
  assignments, and JWT-shaped values;
- `pii.*`: email, selected phone formats, IPv4, national-ID-shaped values, and
  Luhn-valid payment-card-shaped values;
- `format.*`: malformed UTF-8, JSON, or JSONL;
- `sqlite.*`: integrity, open, schema, or table-scan failures;
- `permissions.group_or_other`: group or other POSIX permission bits exist;
- `scan.*`: links, read errors, or resource limits.

### Resource limits

| Option | Default | Enforced maximum |
| --- | ---: | ---: |
| `--max-file-mib` | 16 MiB | 256 MiB |
| `--max-sqlite-rows` | 100,000 | 1,000,000 |
| `--max-sqlite-value-kib` | 1,024 KiB | 16,384 KiB |
| `--max-files` | 10,000 | 100,000 |
| `--max-findings` | 10,000 | 100,000 |

Reaching a file, finding, byte, row, or value limit creates a finding and sets
`complete=false` and `truncated=true`. A bounded scan cannot return healthy just
because uninspected content has not produced a match.

## Project information

ChatArchiveGuard is licensed under the Apache License, Version 2.0. See
[`LICENSE`](LICENSE) and [`PROVENANCE.md`](PROVENANCE.md).

Use synthetic data for contributions. Help and policies are in
[`SUPPORT.md`](SUPPORT.md), [`SECURITY.md`](SECURITY.md),
[`CONTRIBUTING.md`](CONTRIBUTING.md), [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md),
[`CHANGELOG.md`](CHANGELOG.md), and [`RELEASING.md`](RELEASING.md).

Development checks and release procedures stay in the linked contributor and
maintainer documents instead of this user guide.
