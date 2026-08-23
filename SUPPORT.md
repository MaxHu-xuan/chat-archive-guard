# Support

ChatArchiveGuard is an early-stage, community-maintained project. Support is
best effort, with no guaranteed response time.

## Before opening an issue

1. Confirm that Python 3.11 or newer is in use.
2. Check the supported formats and platform table in `README.md`.
3. Confirm that the request is about format integrity, privacy scanning, or scan
   coverage. Message completeness, source attribution, and rotation-sequence
   reconstruction are documented limits rather than built-in checks.
4. Reproduce the behavior with a newly created synthetic archive.
5. Run the unit tests and both privacy-audit commands from `CONTRIBUTING.md`.
6. Search existing GitHub issues for the same fixed finding category.

Use a bug report for reproducible defects and a feature request for proposed
scope changes. Include the package version, Python version, operating-system
family, fixed finding categories, and minimal synthetic steps only. Run with
`--summary-only` before sharing output so relative filenames are omitted.

Never attach or paste real archives, databases, credentials, personal data,
chat excerpts, screenshots, logs, absolute machine paths, or sensitive
filenames. Relative filenames in reports can also be sensitive metadata;
rename synthetic examples before sharing them.

Security vulnerabilities follow `SECURITY.md` and must not be disclosed in a
public support issue.
