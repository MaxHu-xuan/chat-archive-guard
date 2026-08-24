# Release Process

Releases are maintainer-operated. Publishing a Git tag, GitHub release, or
package-index upload is a separate action that requires explicit review.

Before a release:

1. Confirm `pyproject.toml`, `CHANGELOG.md`, and `RELEASE_NOTES.md` describe the
   same candidate version and boundaries. The release notes must still say
   draft until the final candidate is approved.
2. Run the generator self-test, strict tests, and both privacy-audit modes.
   On macOS or Linux:

   ```bash
   PYTHONDONTWRITEBYTECODE=1 python3 scripts/generate_demo.py --self-test
   PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -X dev -W error::ResourceWarning -m unittest discover -s tests -q
   PYTHONDONTWRITEBYTECODE=1 python3 scripts/privacy_audit.py
   PYTHONDONTWRITEBYTECODE=1 python3 scripts/privacy_audit.py --self-test
   ```

   On Windows PowerShell:

   ```powershell
   $env:PYTHONDONTWRITEBYTECODE = "1"
   $previousPythonPath = $env:PYTHONPATH
   $env:PYTHONPATH = "src"
   py -3 scripts\generate_demo.py --self-test
   py -3 -X dev -W error::ResourceWarning -m unittest discover -s tests -q
   py -3 scripts\privacy_audit.py
   py -3 scripts\privacy_audit.py --self-test
   if ($null -eq $previousPythonPath) {
       Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
   } else {
       $env:PYTHONPATH = $previousPythonPath
   }
   ```

3. Build from a clean checkout with the public project timestamp so wheel
   metadata cannot inherit local file times:

   On macOS or Linux:

   ```bash
   export SOURCE_DATE_EPOCH=946684800
   python3 -m venv .venv
   . .venv/bin/activate
   python -m pip install "build==1.3.0" "setuptools==77.0.3" "wheel==0.46.2"
   python -m build --no-isolation
   ```

   On Windows PowerShell:

   ```powershell
   $env:SOURCE_DATE_EPOCH = "946684800"
   py -3 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install "build==1.3.0" "setuptools==77.0.3" "wheel==0.46.2"
   .\.venv\Scripts\python.exe -m build --no-isolation
   ```

   Record all three pinned tool versions. `--no-isolation` prevents the build
   frontend from silently creating another environment with unrecorded backend
   versions.
4. Safely unpack the sdist and run its bundled audit with `--sdist`; install
   the wheel without an index or dependencies in a fresh environment.
5. Exercise both installed entry points and the README's deterministic synthetic
   JSONL/SQLite demo. Confirm exit code `1` is caused by the three intentional
   findings and that summary output contains no filenames or canary values.
6. Never upload the raw setuptools sdist: its tar headers may retain the build
   account and local file times. Create the upload candidate with the bundled
   canonicalizer, using the documented project epoch:

   ```bash
   python3 scripts/canonicalize_sdist.py --self-test
   python3 scripts/canonicalize_sdist.py --dist-dir dist --output-dir canonical-dist --source-date-epoch 946684800
   ```

   Windows PowerShell uses:

   ```powershell
   py -3 scripts\canonicalize_sdist.py --self-test
   py -3 scripts\canonicalize_sdist.py --dist-dir dist --output-dir canonical-dist --source-date-epoch 946684800
   ```

   The canonicalizer fails closed on links, special files, duplicate or unsafe
   paths, and oversized input. It sets uid/gid to zero, removes user/group and
   optional gzip metadata, fixes member times and modes, and verifies that file
   contents are unchanged. Build twice and compare canonical artifact hashes.
7. Review every distributed file, package metadata, changelog, release notes,
   security policy, threat model, SHA-256 checksums, and SBOM.
8. Confirm the final Linux, macOS, and Windows CI matrix is green for the exact
   commit being released. Record final artifact SHA-256 values, SBOM identity,
   canonical-sdist reproducibility, offline installation, and CI evidence in the
   reviewed release draft.

Do not upload archives, databases, messages, credentials, personal data, local
paths, logs, build caches, or private test output. The first public release
should be tagged `v0.1.0` only after its private candidate is approved.
Source publication may proceed without release assets. Only the sdist from
`canonical-dist` may be reviewed for upload; never upload the raw archive from
`dist`.
