# ChatArchiveGuard 0.1.0 release notes

Status: release-candidate draft. Version 0.1.0 has not been tagged, published, or
uploaded from this working tree.

## 中文

ChatArchiveGuard 0.1.0 是首个公开候选版本。它是一道在交付、迁移、共享或分析聊天导出前
运行的本地只读审计门禁，而不是聊天阅读器、导入器或搜索器。

本版本提供：

- 对受支持文本、JSON、JSONL 和 SQLite 内容的本地检查；
- 常见疑似密钥、访问凭证和个人信息格式检测；
- JSON、JSONL 格式校验，以及 SQLite 私有快照与 `PRAGMA quick_check(1)`；
- 明确的扫描覆盖、截断状态和稳定退出码；
- 不含命中值的默认报告，以及省略文件名和明细的 `--summary-only`；
- 只生成固定虚构 JSONL/SQLite 数据的可重复演示；
- Linux、macOS 和 Windows 的持续集成测试。

Windows 标准 Python 缺少本项目要求的原子 no-follow SQLite 打开能力，因此会安全拒绝
SQLite 检查并报告 `sqlite.sidecar_unsafe`，不会降低保护等级。压缩、加密、专有格式、附件
和其他二进制内容不在检查范围内。

工具不能证明消息没有缺失、来源真实、参与者身份可靠或文件从未被修改。匹配结果可能存在
误报和漏报。完整边界见 [`README.md`](README.md) 和
[`THREAT_MODEL.md`](THREAT_MODEL.md)。

首次使用可以直接运行 README 中的[可重复合成演示](README.md#可重复合成演示)。正式安装
应使用经过审核的源码或 wheel；完全离线安装时使用 `--no-index --no-deps`。

## English

ChatArchiveGuard 0.1.0 is the first public release candidate. It is a local,
read-only audit gate to run before delivering, migrating, sharing, or analyzing
chat exports. It is not a chat reader, importer, or search tool.

This release provides:

- local checks for supported text, JSON, JSONL, and SQLite content;
- common potential-secret, credential, and personal-data pattern detection;
- JSON and JSONL validation plus private SQLite snapshots and
  `PRAGMA quick_check(1)`;
- explicit scan coverage, truncation state, and stable exit codes;
- default values-free reports and `--summary-only` output that omits filenames
  and finding rows;
- a reproducible demo that generates only fixed fictional JSONL and SQLite data;
- continuous-integration coverage on Linux, macOS, and Windows.

Standard Python on Windows lacks the atomic no-follow SQLite open required by
this project's boundary. SQLite inspection therefore fails closed as
`sqlite.sidecar_unsafe` instead of weakening protection. Compressed, encrypted,
proprietary, attachment, and other binary content is out of scope.

The tool cannot prove message completeness, source authenticity, participant
identity, or that a file was never altered. Pattern matching can produce false
positives and false negatives. See [`README.md`](README.md) and
[`THREAT_MODEL.md`](THREAT_MODEL.md) for the complete boundary.

Start with the README's
[reproducible synthetic demo](README.md#reproducible-synthetic-demo). Install
only from a reviewed checkout or wheel; use `--no-index --no-deps` when
installation must remain offline.

## Maintainer release evidence

The following evidence must come from the final clean candidate. Do not copy
values from an earlier build or invent placeholders in a published release:

- green Linux, macOS, and Windows CI for the final commit;
- passing unit, generator, canonicalizer, source-tree, and unpacked-sdist
  privacy checks;
- two matching canonical-sdist SHA-256 results from independent builds;
- reviewed wheel and canonical-sdist member lists and metadata;
- SHA-256 checksums and an SBOM generated from the final artifacts;
- successful offline wheel installation and installed-command smoke test.

The maintainer records this evidence in the reviewed release draft before
creating tag `v0.1.0` or uploading any artifact.
