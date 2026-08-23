# Release Process

Releases are maintainer-operated. Publishing a Git tag, GitHub release, or
package-index upload is a separate action that requires explicit review.

Before a release:

1. Run the strict tests and both privacy-audit modes.
2. Build a wheel and source distribution from a clean checkout.
3. Safely unpack the sdist and run its bundled audit with `--sdist`; install
   the wheel without an index or dependencies in a fresh environment.
4. Exercise both installed entry points and a deterministic synthetic scan.
5. Pass the raw build through a reviewed canonical-archive builder using one
   fixed source timestamp, build twice, and compare canonical artifact hashes.
   A raw setuptools sdist may preserve checkout or temporary-file mtimes, so
   matching member contents alone is not evidence of a byte-reproducible
   release archive.
6. Review every distributed file, package metadata, changelog, security policy,
   threat model, SHA-256 checksums, and SBOM.
7. Confirm the final Linux, macOS, and Windows CI matrix is green.

Do not upload archives, databases, messages, credentials, personal data, local
paths, logs, build caches, or private test output. The first public release
should be tagged `v0.1.0` only after its private candidate is approved.
Source publication may proceed without release assets; do not attach a wheel or
sdist or publish to a package index until the canonical artifact gate passes.
