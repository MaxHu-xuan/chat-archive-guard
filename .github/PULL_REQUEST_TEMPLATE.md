## Summary

Describe the behavior changed and why it belongs in this project's documented
scope.

## Verification

- [ ] Unit tests pass on the available platforms.
- [ ] `python scripts/privacy_audit.py` passes.
- [ ] `python scripts/privacy_audit.py --self-test` passes.
- [ ] User-facing or security-relevant changes are documented.

## Data and security checklist

- [ ] Tests and examples use newly generated synthetic data only.
- [ ] No real archive, message, credential, personal data, screenshot, log,
      absolute machine path, sensitive filename, or production configuration
      is included.
- [ ] Output remains values-free and local-only.
- [ ] SQLite no-follow, read-only, fail-closed, and bounded-scan controls are
      unchanged or strengthened.
