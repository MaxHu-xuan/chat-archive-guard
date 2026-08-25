# ChatArchiveGuard 0.1.0 版本说明

## 中文

发布日期：2026 年 8 月 25 日

ChatArchiveGuard 0.1.0 是首个公开版本。它是一道在交付、迁移、共享或分析聊天导出前
运行的本地只读审计门禁，而不是聊天阅读器、导入器或搜索器。

本版本提供：

- 对受支持文本、JSON、JSONL 和 SQLite 内容的本地检查；
- 常见疑似密钥、访问凭证和个人信息形态检测；
- JSON、JSONL 格式校验，以及 SQLite 私有快照与 `PRAGMA quick_check(1)`；
- 明确的扫描覆盖、截断状态和稳定退出码；
- 不包含命中值的默认报告，以及省略文件名和明细的 `--summary-only`；
- 只生成固定虚构 JSONL 和 SQLite 数据的可重复演示；
- Linux、macOS 和 Windows 跨平台验证。

Windows 标准 Python 缺少本项目要求的原子 no-follow SQLite 打开能力，因此会安全拒绝
SQLite 检查并报告 `sqlite.sidecar_unsafe`，不会降低保护等级。压缩、加密、专有格式、附件
和其他二进制内容不在检查范围内。

工具不能证明消息没有缺失、来源真实、参与者身份可靠或文件从未被修改。匹配结果可能存在
误报和漏报。完整边界见
[`README.md`](https://github.com/MaxHu-xuan/chat-archive-guard/blob/main/README.md) 和
[`THREAT_MODEL.md`](https://github.com/MaxHu-xuan/chat-archive-guard/blob/main/THREAT_MODEL.md)。

首次使用可以直接运行 README 中的
[可重复合成演示](https://github.com/MaxHu-xuan/chat-archive-guard/blob/main/README.md#可重复合成演示)。
当 0.1.0 已在 PyPI 提供时，推荐在隔离环境中安装精确版本：

```console
python -m pip install "chat-archive-guard==0.1.0"
```

如果 PyPI 尚未提供该版本，也可以从你已核对的源码仓库安装，或从同一个 GitHub Release
下载 wheel 与 `SHA256SUMS`，核对后按 README 的离线步骤安装。

## English

Release date: August 25, 2026

ChatArchiveGuard 0.1.0 is the first public release. It is a local read-only
audit gate to run before delivering, migrating, sharing, or analyzing chat
exports. It is not a chat reader, importer, or search tool.

This release provides:

- local checks for supported text, JSON, JSONL, and SQLite content;
- detection of common patterns that may indicate secrets, credentials, or
  personal data;
- JSON and JSONL validation plus private SQLite snapshots and
  `PRAGMA quick_check(1)`;
- explicit scan coverage, truncation state, and stable exit codes;
- default reports that never include matched values, plus `--summary-only`
  output that omits filenames and finding rows;
- a reproducible demo that generates only fixed fictional JSONL and SQLite data;
- cross-platform validation on Linux, macOS, and Windows.

Standard Python on Windows lacks the atomic no-follow file opening required by
this project's SQLite safety boundary. SQLite inspection therefore fails closed
as `sqlite.sidecar_unsafe` instead of weakening protection. Compressed or
encrypted files, proprietary formats, attachments, and other binary content are
out of scope.

The tool cannot prove message completeness, source authenticity, participant
identity, or that a file was never altered. Pattern matching can produce false
positives and false negatives. See
[`README.md`](https://github.com/MaxHu-xuan/chat-archive-guard/blob/main/README.md)
and
[`THREAT_MODEL.md`](https://github.com/MaxHu-xuan/chat-archive-guard/blob/main/THREAT_MODEL.md)
for the complete boundary.

Start with the README's
[reproducible synthetic demo](https://github.com/MaxHu-xuan/chat-archive-guard/blob/main/README.md#reproducible-synthetic-demo).
When version 0.1.0 is available on PyPI, install the exact release in an isolated
environment:

```console
python -m pip install "chat-archive-guard==0.1.0"
```

If PyPI does not yet provide the release, install from a source checkout you
have verified, or download the wheel and `SHA256SUMS` from the same GitHub
Release and follow the README's offline verification and installation steps.
