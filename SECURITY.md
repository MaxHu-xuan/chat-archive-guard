# Security policy

## Supported state

This project is pre-1.0 security software. Do not expose it as a privileged
service or run it against an untrusted, concurrently mutated filesystem.
Security fixes are provided on a best-effort basis for the latest published
pre-1.0 release and the current default branch. Older revisions are not
supported.

## Reporting a vulnerability

Use GitHub's private vulnerability-reporting control on the repository
`Security` page when it is available. If GitHub does not show that control,
use the repository's `Private security coordination request` issue form. That
public form is only for asking the maintainer to establish a private channel;
do not describe the vulnerability there.

Do not include real credentials, personal data, chat excerpts, databases,
archive filenames, screenshots, logs, or absolute machine paths. Use a minimal
synthetic reproducer and identify only the affected version, operating-system
family, Python version, and fixed finding category. Never test against systems
or data you are not authorized to access.

Acknowledgement and remediation timing depend on severity and maintainer
availability. No response-time or disclosure-date guarantee is made.

## Operational guidance

- Run as an unprivileged account with read access only to the intended archive.
- Keep the scan root narrow; do not scan an entire home or system directory.
- Treat relative filenames in default reports as potentially sensitive metadata;
  use `--summary-only` when paths are unnecessary.
- Do not redirect reports into the archive being scanned.
- Keep SQLite WAL and SHM files together with the database so committed WAL
  records remain visible in the private snapshot.
- Do not add real data to tests, examples, issue reports, or CI artifacts.
- Run both bundled privacy-audit modes before every release candidate:
  `PYTHONDONTWRITEBYTECODE=1 python scripts/privacy_audit.py` and
  `PYTHONDONTWRITEBYTECODE=1 python scripts/privacy_audit.py --self-test`.
- Run the same checks with `--sdist` against the unpacked source distribution;
  that mode permits and inspects only `src/chat_archive_guard.egg-info`.
- Review source provenance and Apache-2.0 compatibility before every release.

The scanner never intentionally writes to the source tree. Where
`O_NOFOLLOW` is available, it obtains no-follow read descriptors for the
database and present WAL/SHM sidecars, copies them to a private temporary
directory, verifies their identity and content stability, and opens only the
copy with SQLite. Inspection then occurs on an in-memory backup. If
`O_NOFOLLOW` is unavailable, SQLite inspection returns the values-free
`sqlite.sidecar_unsafe` finding without opening SQLite; it does not silently
fall back to a race-prone source open. POSIX mode findings do not claim to
audit Windows ACLs.

The privacy audit is a release preflight rather than a sandbox. Passing it does
not authorize running unreviewed contributions, and it cannot prove the
absence of dynamically constructed network or process access.
