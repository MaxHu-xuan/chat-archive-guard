# Release Process

Releases are maintainer-operated. Publishing a Git tag, GitHub release, or
package-index upload is a separate action that requires explicit review.

Before a release:

1. Run the strict tests and both privacy-audit modes.
2. Build from a clean checkout with the public project timestamp so wheel
   metadata cannot inherit local file times:

   - macOS or Linux: `export SOURCE_DATE_EPOCH=946684800`
   - Windows PowerShell: `$env:SOURCE_DATE_EPOCH = "946684800"`

   Then run `python -m build`.
3. Safely unpack the sdist and run its bundled audit with `--sdist`; install
   the wheel without an index or dependencies in a fresh environment.
4. Exercise both installed entry points and a deterministic synthetic scan.
5. Never upload the raw setuptools sdist: its tar headers may retain the build
   account and local file times. Create the upload candidate with the bundled
   canonicalizer, using the documented project epoch:

   ```bash
   python scripts/canonicalize_sdist.py --self-test
   python scripts/canonicalize_sdist.py --dist-dir dist --output-dir canonical-dist --source-date-epoch 946684800
   ```

   The canonicalizer fails closed on links, special files, duplicate or unsafe
   paths, and oversized input. It sets uid/gid to zero, removes user/group and
   optional gzip metadata, fixes member times and modes, and verifies that file
   contents are unchanged. Build twice and compare canonical artifact hashes.
6. Review every distributed file, package metadata, changelog, security policy,
   threat model, SHA-256 checksums, and SBOM.
7. Confirm the final Linux, macOS, and Windows CI matrix is green.

Do not upload archives, databases, messages, credentials, personal data, local
paths, logs, build caches, or private test output. The first public release
should be tagged `v0.1.0` only after its private candidate is approved.
Source publication may proceed without release assets. Only the sdist from
`canonical-dist` may be reviewed for upload; never upload the raw archive from
`dist`.
