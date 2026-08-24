# ChatArchiveGuard（聊天归档守护）

[![CI](https://github.com/MaxHu-xuan/chat-archive-guard/actions/workflows/ci.yml/badge.svg)](https://github.com/MaxHu-xuan/chat-archive-guard/actions/workflows/ci.yml)

[中文说明](#中文说明) | [English overview](#english-overview) |
[中文技术参考](#中文技术参考) | [English technical reference](#english-technical-reference)

## 中文说明

准备保存、迁移、共享或分析聊天导出时，可以先让 ChatArchiveGuard（聊天归档守护）在
自己的电脑上做一次只读检查：

- 找出疑似密钥、访问凭证和个人信息格式；
- 发现损坏的 UTF-8、JSON 或 JSONL；
- 检查 SQLite 是否能安全读取、结构是否通过快检，并扫描可读文本；
- 用隐私安全摘要说明发现了什么、扫了多少、是否留下盲区。

扫描器只读取你指定的文件或目录，不修改原文件，也不上传数据。使用 `--summary-only` 时，
报告只保留真实状态、数量和类别，不包含文件名或命中值。默认报告仍会显示相对文件名，方便
本地定位问题。运行时没有网络客户端、遥测或自动更新功能。

它是一道面向交付或迁移前检查的审计门禁，不是聊天归档阅读器、导入器、搜索器，也不能
证明消息业务完整或来源真实。

[先看一分钟合成演示](#可重复合成演示)，或[比较三个相关工具](#三个项目怎么选)。

### 用户价值

一次扫描可以回答三个实际问题：

1. 支持的文件中是否出现常见密钥、凭证或个人信息形态；
2. JSON、JSONL 和 SQLite 等内容是否能按预期读取，SQLite 快检是否通过；
3. 本次符合检查范围的内容是否全部完成扫描，是否有链接、读取错误或资源上限留下盲区。

这里的聊天归档完整性指文件格式、SQLite 结构和本次扫描覆盖状态。它不等于消息完整性，
也不能证明归档没有丢消息、来源真实或文件从未被篡改。

### 三个项目怎么选

| 你的问题 | 选择 |
| --- | --- |
| 分享或迁移聊天导出前，本地检查疑似秘密、个人信息形态、格式、SQLite 与扫描盲区 | ChatArchiveGuard（聊天归档守护），当前项目 |
| 确认最终 PPTX 及随附验收证据仍匹配结构检查后生成的 HMAC 签名收据 | [ArtifactProof（PPTX 交付物验真）](https://github.com/MaxHu-xuan/artifactproof) |
| 重启后核对卡住任务、超时与待投递状态，不把未知结果猜成成功 | [TaskStateGuard（任务状态守护）](https://github.com/MaxHu-xuan/task-state-guard) |

三个工具解决的是不同问题，可以单独使用；ChatArchiveGuard 不负责 PPTX 验真或任务状态修复。

### 适用场景

- 在把聊天导出交给分析、迁移或备份流程前，先做一次本地隐私审计。
- 检查文本、JSON、JSONL 或 NDJSON 导出是否存在格式错误和常见敏感信息形态。
- 检查 SQLite 聊天数据库、WAL 中已提交但尚未归并的记录，以及可读取的 FTS 文本。
- 扫描一个目录中的多份当前日志和轮转日志，并明确哪些文件真正进入了内容检查。
- 在 CI 或离线工作站中用固定退出码和聚合摘要执行交付前门禁。

### 完整性检查

ChatArchiveGuard 会按文件类型执行不同检查：

- 文本、JSON 和 JSONL：检查 UTF-8 与结构格式，并扫描支持内容中的常见秘密和个人信息形态。
- SQLite：对私有快照运行 `PRAGMA quick_check(1)`，扫描普通表和可访问的 FTS 虚拟表文本；
  FTS 影子表不会重复计数。
- WAL 和 SHM：只与对应主数据库一起复制到私有临时目录，再由 SQLite 打开副本。
- 目录覆盖：用 `files_seen`、`files_scanned`、`complete` 和 `truncated` 区分遍历范围与实际
  内容检查范围。

轮转日志会作为独立文件处理。只有最终扩展名属于支持范围的文件，例如 `history.1.log`，
才会进入文本扫描；`history.log.1` 和压缩后的 `.gz` 文件不会被自动识别为文本。工具不会
拼接轮转序列，也不会判断时间段是否连续。

### 隐私与安全

- 扫描在本机完成，运行时只使用 Python 标准库。
- 工具不会修改源文件或源数据库；SQLite 只从经过复核的私有副本读取。
- 命中值不会进入报告，读取异常也只映射为固定类别。
- 符号链接、类似链接的入口、并发变化和无法安全读取的 SQLite 会被拒绝或标记为不完整。
- 文件数量、文本字节、SQLite 行数、单值大小和发现数量都有硬上限。

默认报告中的相对文件名仍是元数据。使用 `--summary-only` 后，JSON 和文本输出都会省略
全部发现明细与相对文件名，只保留真实状态、扫描计数和类别汇总，适合 CI 或分享
脱敏报告。无论使用哪种报告模式，退出码和 `finding_count` 都不会被改写。

摘要模式不会建立用户或渠道隔离。类别计数仍然汇总整个扫描根目录，因此调用者应先把根
目录限制在自己有权检查的单个数据集，不要用一个跨用户目录生成共享摘要。

### 快速开始

需要 Python 3.11 或更高版本。当前版本尚未发布到包索引，请从已经审核的源码或 wheel
安装。

macOS 或 Linux 从源码目录安装：

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
```

```console
chat-archive-guard /path/to/archive
chat-archive-guard /path/to/archive --json --summary-only
```

Windows PowerShell 使用 Python Launcher 和不同的路径写法：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\python.exe -m chat_archive_guard C:\path\to\archive
.\.venv\Scripts\python.exe -m chat_archive_guard C:\path\to\archive --json --summary-only
```

同时查看退出码和 `ok`、`complete`、`truncated`。只有没有发现项、扫描完整且未截断时，
`ok` 才会是 `true`。

若已经拿到审核过的 wheel，可以避免索引访问和依赖解析：

```console
python -m pip install --no-index --no-deps /path/to/chat_archive_guard-0.1.0-py3-none-any.whl
```

Windows PowerShell 的离线 wheel 安装命令为：

```powershell
.\.venv\Scripts\python.exe -m pip install --no-index --no-deps C:\path\to\chat_archive_guard-0.1.0-py3-none-any.whl
```

未安装时，macOS 和 Linux 可以从源码目录运行：

```console
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m chat_archive_guard /path/to/archive --json
```

Windows PowerShell 使用不同的环境变量语法：

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:PYTHONPATH = "src"
py -3 -m chat_archive_guard C:\path\to\archive --json
```

### 可重复合成演示

仓库附带的生成器只创建两份固定的虚构数据：一份 JSONL 和一份 SQLite。它不会读取现有
文件，也不会覆盖已有目录。演示中的测试标记都明确写着永不有效，只用于证明检查器确实能
发现问题，不是可用凭据，也不来自任何真实对话。

macOS 或 Linux（在仓库根目录执行）：

```console
demo_parent="$(mktemp -d)"
demo_parent="$(cd "$demo_parent" && pwd -P)"
demo_dir="$demo_parent/chat-archive-guard-demo"
PYTHONDONTWRITEBYTECODE=1 python3 scripts/generate_demo.py "$demo_dir"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m chat_archive_guard "$demo_dir" --summary-only
```

实测输出如下：

```text
synthetic demo: PASS files=2
FAIL files_seen=2 files_scanned=2 finding_count=3 complete=true truncated=false details_omitted=true findings_omitted=true
category=format.invalid_jsonl count=1
category=secret.assignment count=1
category=secret.provider_key count=1
```

Windows PowerShell（在仓库根目录执行）：

```powershell
$demoDir = Join-Path ([System.IO.Path]::GetTempPath()) ("chat-archive-guard-demo-" + [guid]::NewGuid())
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:PYTHONPATH = "src"
py -3 scripts/generate_demo.py $demoDir
py -3 -m chat_archive_guard $demoDir --summary-only
```

Windows 的文本检查结果相同，但标准 Python 会按安全边界拒绝直接检查 SQLite，因此输出为：

```text
synthetic demo: PASS files=2
FAIL files_seen=2 files_scanned=1 finding_count=3 complete=false truncated=true details_omitted=true findings_omitted=true
category=format.invalid_jsonl count=1
category=secret.assignment count=1
category=sqlite.sidecar_unsafe count=1
```

两组扫描命令的退出码都会按设计返回 `1`，因为演示数据故意包含三个发现项。这表示门禁
发现了问题，不表示生成器或扫描器运行失败。演示结束后可以删除刚创建的唯一临时目录。

### 看懂结果

| 内容 | 含义 |
| --- | --- |
| 退出码 `0` | 没有发现项，并且符合范围的内容完成扫描 |
| 退出码 `1` | 发现问题，或有符合范围的内容未能完整检查 |
| 退出码 `2` | 扫描路径或参数无效 |
| `files_seen` | 遍历到的常规文件数量，包括不支持内容检查的文件 |
| `files_scanned` | 已进入受支持内容检查阶段的文件数量 |
| `finding_count` | 所有类别的真实发现总数，包括摘要模式省略的明细 |
| `complete` | 符合当前检查范围的内容是否全部完成检查 |
| `truncated` | 是否因限制、读取失败或安全拒绝留下未检查内容 |
| `findings` | 默认报告中的相对路径、固定类别和数量，不含命中值 |
| `details_omitted`、`findings_omitted` | 摘要模式明确表示明细和文件名已省略 |

下面是默认 JSON 模式扫描一个合成无效文件后的完整结果。
`format.invalid_json` 表示 JSON 格式错误：

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

`complete=true` 只表示符合当前范围的内容完成检查，不代表聊天记录在业务上完整，也不代表
工具能证明文件中不存在任何敏感信息。

### 平台差异

| 能力 | Linux | macOS | Windows |
| --- | --- | --- | --- |
| 文本、JSON、JSONL 检查 | 支持 | 支持 | 支持 |
| SQLite、WAL、SHM 检查 | 提供 `O_NOFOLLOW` 时支持 | 提供 `O_NOFOLLOW` 时支持 | 标准 Python 下安全拒绝 |
| 文件权限检查 | POSIX 权限位 | POSIX 权限位 | 不推断或审计 ACL |
| 链接防护 | 拒绝或跳过符号链接 | 拒绝或跳过符号链接 | 拒绝或跳过重解析点及类似入口 |

Windows 标准库 Python 没有本项目安全边界要求的原子 no-follow 打开能力。遇到 SQLite 时，
工具会返回 `sqlite.sidecar_unsafe`，并设置 `complete=false`、`truncated=true`，不会降低保护
等级后继续读取。

### 使用局限

内容检查覆盖 `.txt`、`.md`、`.log`、`.csv`、`.tsv`、`.yaml`、`.yml`、`.json`、
`.jsonl` 和 `.ndjson`。`.db`、`.sqlite`、`.sqlite3` 以及带 SQLite 文件头的文件会按
SQLite 处理。

压缩包、加密文件、专有格式、附件、图片、音频和其他二进制内容不在检查范围内。这些常规
文件仍计入 `files_seen`，并在 POSIX 系统上接受权限检查，但不计入 `files_scanned`。

工具不会验证消息完整性（message completeness）、来源归属（source attribution）、导出
时间范围、参与者身份或平台签名。它也不是聊天阅读器、备份恢复工具、杀毒软件、OCR 工具、
取证工具或完整的数据防泄漏系统。匹配结果只是风险提示，可能存在误报和漏报。

### 常见问题

#### 会上传聊天数据吗？

不会。安装后的扫描器只读取本地路径，没有网络客户端或遥测。常规安装可能访问包索引；
需要完全离线时，请使用审核过的 wheel 和前述 `--no-index --no-deps` 命令。

#### 能检查所有聊天导出吗？

不能。工具只检查支持的文本、JSON、JSONL 和 SQLite 内容，不要求文件来自特定应用。
压缩、加密、专有格式和附件内容不受支持。

#### 能验证消息完整性和来源归属吗？

不能。工具可以报告文件格式、SQLite 快检和扫描覆盖状态，但无法知道平台是否漏导、记录
是否被删除，也不能认证某条消息来自哪个平台、账户或设备。需要这类结论时，应另外保存并
核对原始来源、耐久记录、可读归档、记录计数、时间范围、导出签名或可信来源回执，并对
轮转来源的归属冲突采用安全拒绝策略。本项目不建立或修复这些跨层关系。

#### 如何处理轮转日志（rotated logs）？

把需要检查的未压缩日志放在同一扫描根目录下，并确保最终扩展名是 `.log`。每份文件会独立
扫描，但工具不会还原轮转顺序、去重或证明时间覆盖连续。压缩日志需要先在受控目录中安全
解包，解包能力不属于本项目。工具也不会根据文件名推断日志属于哪个用户、渠道或来源。

#### 没有发现项就代表绝对安全吗？

不代表。完整且无发现的结果只说明已检查内容没有触发当前规则。未知模式、不支持的格式、
语义重识别和检测器漏报仍然可能存在。

#### 可以在 CI 中使用吗？

可以，但 CI 必须有权读取输入。建议使用 `--json --summary-only` 读取真实状态与类别汇总，
避免在构建日志中暴露相对文件名。不要把真实聊天内容上传为公开构建产物。本项目自己的 CI
只使用运行时生成的合成数据。

## 中文技术参考

### 工作原理

1. 工具只遍历指定文件或目录。扫描根路径的链接型入口会被拒绝，目录内的链接会被报告但
   不会跟随。
2. 文本检测器只累计类别数量，不保留命中值。JSON 和 JSONL 同时接受格式校验。
3. 在支持原子 no-follow 打开的系统上，SQLite 主文件和现有 WAL、SHM 会复制到权限为
   `0700` 的临时目录和权限为 `0600` 的临时文件。工具重新校验来源身份和 SHA-256，
   只让 SQLite 打开私有副本，再在内存备份上运行 `PRAGMA quick_check(1)` 和内容检查。
4. FTS 虚拟表内容只检查一次，FTS 影子表不会重复计数。来源发生并发变化、读取失败或达到
   限制时，结果会明确标为不完整。

扫描器只使用 Python 标准库。完整边界和残余风险见
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
`complete=false`、`truncated=true`。有限扫描不会因为未检查内容暂时没有命中而返回健康
结果。

## English overview

Before you store, migrate, share, or analyze a chat export, run ChatArchiveGuard
locally to:

- flag common secret, credential, and personal-data patterns;
- find malformed UTF-8, JSON, or JSONL;
- check whether SQLite can be read safely, passes its integrity check, and
  contains readable text worth reviewing; and
- produce a privacy-safer summary of findings, coverage, and blind spots.

The scanner reads only the file or directory you choose. It does not modify the
source or upload data. With `--summary-only`, the report keeps real status,
counts, and categories while omitting filenames and matched values. Default
reports retain relative filenames for local troubleshooting. The runtime has no
network client, telemetry, or automatic update check.

It is a pre-delivery or pre-migration audit gate, not a chat archive reader,
importer, search tool, or proof of message completeness or source authenticity.

[Try the one-minute synthetic demo](#reproducible-synthetic-demo), or
[compare the three related tools](#which-project-should-i-use).

### User value

One scan answers three practical questions:

1. Do supported files contain common secret, credential, or personal-data
   patterns?
2. Can JSON, JSONL, and SQLite content be read as expected, and does SQLite pass
   its integrity check?
3. Did every eligible item finish scanning, or did links, read errors, or
   resource limits leave a blind spot?

Chat archive integrity here means format integrity, SQLite structural integrity,
and scan coverage. It does not mean message completeness, source authenticity,
or proof that a file was never altered.

### Which project should I use?

| Your question | Choose |
| --- | --- |
| Before sharing or migrating a chat export, locally audit potential secrets, personal-data patterns, format or SQLite issues, and scan gaps | ChatArchiveGuard, this project |
| Verify that a final PPTX and its supplied QA evidence still match the HMAC-signed receipt created after structural checks | [ArtifactProof](https://github.com/MaxHu-xuan/artifactproof) |
| After a restart, reconcile stuck tasks, timeouts, and pending delivery without guessing success | [TaskStateGuard](https://github.com/MaxHu-xuan/task-state-guard) |

Each tool addresses a separate problem and can be used independently.
ChatArchiveGuard does not validate PPTX artifacts or repair task state.

### Use cases

- Run a local chat export privacy audit before analysis, migration, or backup.
- Validate text, JSON, JSONL, or NDJSON exports and scan supported content for
  common sensitive-data patterns.
- Inspect a SQLite chat database, committed records still visible in WAL, and
  readable text in FTS virtual tables.
- Scan current and rotated log files in one directory while seeing which files
  actually entered content inspection.
- Use stable exit codes and aggregate JSON summaries as an offline or CI
  pre-delivery gate.

### Integrity checks

Checks depend on the file type:

- Text, JSON, and JSONL: validate UTF-8 and structure, then scan eligible content
  for common secret and personal-data patterns.
- SQLite: run `PRAGMA quick_check(1)` on a private snapshot and inspect readable
  text in regular and available FTS virtual tables. FTS shadow tables are not
  counted twice.
- WAL and SHM: copy present sidecars with their main database into a private
  temporary directory before SQLite opens the copy.
- Directory coverage: use `files_seen`, `files_scanned`, `complete`, and
  `truncated` to distinguish traversal from completed content inspection.

Rotated logs are treated as separate files. Only a file whose final extension
is supported, such as `history.1.log`, enters text scanning. A file such as
`history.log.1`, or a compressed `.gz` log, is not recognized as text. The tool
does not join a rotation sequence or decide whether its time range is continuous.

### Privacy and security

- Scanning stays on the local machine and the runtime uses only the Python
  standard library.
- Source files and databases are not modified. SQLite reads only a reviewed
  private copy.
- Matched values never enter a report, and read failures map to fixed categories.
- Symlinks, link-like entries, concurrent changes, and SQLite files that cannot
  be opened safely are rejected or make the result incomplete.
- Hard limits bound file count, text bytes, SQLite rows, individual values, and
  retained findings.

Relative filenames in default reports remain metadata. With `--summary-only`,
JSON and text output omit every finding row and relative filename while keeping
the real status, coverage counts, and category totals. Exit codes and
`finding_count` do not change. This mode is intended for CI and safer report
sharing.

Summary-only mode does not create user or channel isolation. Category totals
still cover the entire scan root. Limit the root to one dataset you are
authorized to inspect before sharing an aggregate report.

### Quick start

Python 3.11 or newer is required. The project has not yet been published to a
package index, so install from a reviewed checkout or wheel.

On macOS or Linux, install from the source directory:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
```

```console
chat-archive-guard /path/to/archive
chat-archive-guard /path/to/archive --json --summary-only
```

Windows PowerShell uses Python Launcher and Windows path syntax:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\python.exe -m chat_archive_guard C:\path\to\archive
.\.venv\Scripts\python.exe -m chat_archive_guard C:\path\to\archive --json --summary-only
```

Read the exit code together with `ok`, `complete`, and `truncated`. `ok` is
`true` only when there are no findings and the eligible scan completed without
truncation.

With a reviewed wheel, installation can avoid index access and dependency
resolution:

```console
python -m pip install --no-index --no-deps /path/to/chat_archive_guard-0.1.0-py3-none-any.whl
```

On Windows PowerShell, install a reviewed wheel offline with:

```powershell
.\.venv\Scripts\python.exe -m pip install --no-index --no-deps C:\path\to\chat_archive_guard-0.1.0-py3-none-any.whl
```

Without installation, macOS and Linux can run from the checkout:

```console
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m chat_archive_guard /path/to/archive --json
```

Windows PowerShell uses a different environment-variable syntax:

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:PYTHONPATH = "src"
py -3 -m chat_archive_guard C:\path\to\archive --json
```

### Reproducible synthetic demo

The bundled generator creates exactly two fixed, fictional files: one JSONL
file and one SQLite database. It does not read existing files or overwrite an
existing directory. Every test marker is visibly marked as invalid and exists only
to prove that findings work; none is a usable credential or real conversation.

On macOS or Linux, run from the repository root:

```console
demo_parent="$(mktemp -d)"
demo_parent="$(cd "$demo_parent" && pwd -P)"
demo_dir="$demo_parent/chat-archive-guard-demo"
PYTHONDONTWRITEBYTECODE=1 python3 scripts/generate_demo.py "$demo_dir"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m chat_archive_guard "$demo_dir" --summary-only
```

Observed output:

```text
synthetic demo: PASS files=2
FAIL files_seen=2 files_scanned=2 finding_count=3 complete=true truncated=false details_omitted=true findings_omitted=true
category=format.invalid_jsonl count=1
category=secret.assignment count=1
category=secret.provider_key count=1
```

On Windows PowerShell, run from the repository root:

```powershell
$demoDir = Join-Path ([System.IO.Path]::GetTempPath()) ("chat-archive-guard-demo-" + [guid]::NewGuid())
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:PYTHONPATH = "src"
py -3 scripts/generate_demo.py $demoDir
py -3 -m chat_archive_guard $demoDir --summary-only
```

Text scanning produces the same findings. Standard Python on Windows safely
refuses direct SQLite inspection, so the output is:

```text
synthetic demo: PASS files=2
FAIL files_seen=2 files_scanned=1 finding_count=3 complete=false truncated=true details_omitted=true findings_omitted=true
category=format.invalid_jsonl count=1
category=secret.assignment count=1
category=sqlite.sidecar_unsafe count=1
```

Both scan commands intentionally return exit code `1` because the demo contains
three findings. That means the gate detected the canaries; it does not mean that
generation or scanning crashed. Delete only the unique temporary directory you
created when the demo is complete.

### Read the result

| Item | Meaning |
| --- | --- |
| Exit code `0` | No findings and every eligible item completed scanning |
| Exit code `1` | A finding exists or eligible content was not fully inspected |
| Exit code `2` | The scan path or arguments are invalid |
| `files_seen` | Regular files encountered, including unsupported content |
| `files_scanned` | Files that entered a supported content-inspection path |
| `finding_count` | The true total across categories, including omitted detail rows |
| `complete` | Whether all eligible content completed inspection |
| `truncated` | Whether a limit, read failure, or safety refusal left content unchecked |
| `findings` | Relative paths, fixed categories, and counts in the default report |
| `details_omitted`, `findings_omitted` | Summary-mode flags confirming that details and filenames were omitted |

This complete default JSON example uses a synthetic malformed file.
`format.invalid_json` identifies the format error:

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

`complete=true` means only that eligible content completed the configured scan.
It does not mean that the conversation is complete or that every sensitive-data
shape is absent.

### Platform behavior

| Capability | Linux | macOS | Windows |
| --- | --- | --- | --- |
| Text, JSON, and JSONL | Supported | Supported | Supported |
| SQLite, WAL, and SHM | Supported when `O_NOFOLLOW` exists | Supported when `O_NOFOLLOW` exists | Safely refused by standard Python |
| Permission check | POSIX mode bits | POSIX mode bits | Does not infer or audit ACLs |
| Link handling | Reject or skip symlinks | Reject or skip symlinks | Reject or skip reparse points and similar entries |

Standard Python on Windows does not provide the atomic no-follow open required
by this project's SQLite boundary. A SQLite input returns
`sqlite.sidecar_unsafe` with `complete=false` and `truncated=true`; the scanner
does not continue with weaker protection.

### Limitations

Content inspection covers `.txt`, `.md`, `.log`, `.csv`, `.tsv`, `.yaml`,
`.yml`, `.json`, `.jsonl`, and `.ndjson`. Files ending in `.db`, `.sqlite`, or
`.sqlite3`, or carrying the SQLite header, are treated as databases.

Compressed, encrypted, proprietary, attachment, image, audio, and other binary
content is unsupported. Those regular files still contribute to `files_seen`
and receive the POSIX permission check, but do not enter `files_scanned`.

The tool does not verify message completeness, source attribution, export date
coverage, participant identity, or platform signatures. It is not a chat
reader, backup-restoration tool, antivirus scanner, OCR system, forensic tool,
or complete data-loss-prevention product. Pattern matches are indicators and
can produce false positives or false negatives.

### FAQ

#### Does ChatArchiveGuard upload chat data?

No. The installed scanner reads local paths and contains no network client or
telemetry. A normal installation may contact a package index. Use a reviewed
wheel with `--no-index --no-deps` when installation must remain offline.

#### Can it scan every chat export?

No. It inspects supported text, JSON, JSONL, and SQLite content without requiring
a specific source application. Compressed, encrypted, proprietary, and
attachment content is out of scope.

#### Can it verify message completeness or source attribution?

No. It reports format integrity, SQLite integrity checks, and scan coverage. It
cannot know whether a platform omitted records, whether someone deleted a
message, or whether a record came from a claimed platform, account, or device.
For those questions, separately reconcile original sources, a durable record,
the readable archive, record counts, date ranges, export signatures, or trusted
source receipts. Conflicting ownership for rotated sources should fail closed.
ChatArchiveGuard does not build or repair those cross-layer relationships.

#### How should I scan rotated logs?

Place the uncompressed logs you are authorized to inspect under one narrow scan
root and make sure each final extension is `.log`. Each file is scanned
independently. ChatArchiveGuard does not reconstruct rotation order, remove
duplicates, or prove continuous time coverage. Safe archive extraction remains
the caller's responsibility. It also does not infer a log's user, channel, or
source from its filename.

#### Does a clean result prove that an archive is safe?

No. A clean, complete result means no configured detector fired in eligible
content that completed inspection. Unsupported formats, unknown patterns,
semantic re-identification, and detector false negatives remain possible.

#### Can it run in CI?

Yes, when the CI system is authorized to read the input. Use
`--json --summary-only` to retain real status and category counts without
placing relative filenames in build logs. Never upload real conversations as
public workflow artifacts. This project's CI uses only synthetic runtime data.

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
[`CHANGELOG.md`](CHANGELOG.md), [`RELEASE_NOTES.md`](RELEASE_NOTES.md), and
[`RELEASING.md`](RELEASING.md).

Development checks and release procedures stay in the linked contributor and
maintainer documents instead of this user guide.
