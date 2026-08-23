# Contributing

Thank you for improving ChatArchiveGuard.

## License for contributions

Unless you explicitly state otherwise, any contribution intentionally
submitted for inclusion in this project is provided under the Apache License,
Version 2.0, without additional terms or conditions. See `LICENSE`.

No Developer Certificate of Origin sign-off, real name, personal email address,
or other personal information is required by this project. Do not add sign-off
lines unless you independently choose to do so.

## Data-safety rules

- Use synthetic data created specifically for tests and documentation.
- Never submit credentials, tokens, private keys, personal data, chat excerpts,
  production databases, logs, screenshots, archive filenames, or machine paths.
- Keep examples offline and deterministic; do not add network access or
  telemetry.
- Make diagnostics values-free: report categories and counts, not matched
  content or exception messages.
- Preserve `--summary-only` as an aggregate-only mode: no finding rows or
  relative filenames, with unchanged status, counts, categories, and exit code.

Before submitting a change, run:

```console
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src PYTHONWARNINGS=error::ResourceWarning python -X dev -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 python scripts/privacy_audit.py
PYTHONDONTWRITEBYTECODE=1 python scripts/privacy_audit.py --self-test
```

Hosted CI runs Linux across Python 3.11-3.14 plus Python 3.11 and 3.14 boundary
jobs on macOS and Windows. In PowerShell, set `PYTHONDONTWRITEBYTECODE` and
`PYTHONPATH=src` through `$env:` before running the same Python commands:

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:PYTHONPATH = "src"
python -X dev -W error::ResourceWarning -m unittest discover -s tests -v
python scripts/privacy_audit.py
python scripts/privacy_audit.py --self-test
```

## Change expectations

- Keep changes focused and document user-visible behavior in `README.md` and
  `CHANGELOG.md`.
- Add Linux, macOS, and Windows coverage when behavior differs by platform.
- Preserve the finite scan limits and fixed, values-free error categories.
- Do not weaken SQLite no-follow copying, source-identity checks, read-only
  opening, in-memory inspection, or fail-closed behavior.
- Do not add network access, telemetry, analytics, or automatic updates.
- Do not commit generated packages, caches, environments, coverage data, or
  persistent archive fixtures.

Pull requests should use the repository template. Security vulnerabilities
must follow `SECURITY.md`, not a public pull request or issue.
