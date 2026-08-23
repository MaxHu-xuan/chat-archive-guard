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

Before submitting a change, run:

```console
PYTHONPATH=src python -m unittest discover -s tests -v
python scripts/privacy_audit.py
```

Hosted CI runs Linux across Python 3.11-3.14 plus Python 3.11 and 3.14 boundary
jobs on macOS and Windows. In PowerShell, set `PYTHONDONTWRITEBYTECODE` and
`PYTHONPATH=src` through `$env:` before running the same Python commands.
