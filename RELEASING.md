# Release Process

Version 0.1.0 has release date 2026-08-25. Releases are maintainer-operated.
Creating a tag, publishing a GitHub Release, approving a protected environment,
and uploading to PyPI are distinct reviewed actions.

## One-time Trusted Publishing setup

Before the first PyPI upload:

1. Create a GitHub environment named `pypi`. Require a maintainer reviewer,
   restrict deployment branches and tags to the intended release policy, and
   do not add an environment secret or allow unreviewed administrator bypass.
2. In PyPI, create the project or a pending Trusted Publisher with these exact
   values:

   - PyPI project: `chat-archive-guard`
   - GitHub owner: `MaxHu-xuan`
   - GitHub repository: `chat-archive-guard`
   - workflow filename: `publish-pypi.yml`
   - environment: `pypi`

   A pending publisher does not reserve the project name. Configure it only as
   part of the reviewed first-release window.
3. Keep `.github/workflows/publish-pypi.yml` pinned to reviewed full commit
   SHAs. Publishing uses GitHub OIDC and PyPI Trusted Publishing; it must not
   use a PyPI API token, password, or repository secret.

The `verify` job has only `contents: read` and cannot request an OIDC token.
Its release-asset downloader accepts only this repository's GitHub API asset
URLs, follows exactly one unauthenticated HTTPS redirect to a
`githubusercontent.com` subdomain, rejects any further redirect, and then
checks the declared size and reviewed hash. The repository token is never sent
to the redirected host.

The environment-gated `publish` job has only `id-token: write`, defines no
checkout or repository-authored `run` step, and contains only the pinned
artifact-download and PyPA publisher actions for the verified workflow
artifact.

## Prepare and test the release source

1. Confirm `pyproject.toml`, `CHANGELOG.md`, and `RELEASE_NOTES.md` all
   describe version 0.1.0 and release date 2026-08-25. Review every distributed
   file, package metadata field, security boundary, and release note.
2. Run the generator and canonicalizer self-tests, strict unit tests, and both
   privacy-audit modes.

   On macOS or Linux:

   ```bash
   PYTHONDONTWRITEBYTECODE=1 python3 scripts/generate_demo.py --self-test
   PYTHONDONTWRITEBYTECODE=1 python3 scripts/canonicalize_sdist.py --self-test
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
   py -3 scripts\canonicalize_sdist.py --self-test
   py -3 -X dev -W error::ResourceWarning -m unittest discover -s tests -q
   py -3 scripts\privacy_audit.py
   py -3 scripts\privacy_audit.py --self-test
   if ($null -eq $previousPythonPath) {
       Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
   } else {
       $env:PYTHONPATH = $previousPythonPath
   }
   ```

3. Confirm the final Linux, macOS, and Windows CI matrix is green for the exact
   commit. Exercise the README's deterministic JSONL/SQLite demo and confirm
   exit code 1 is caused only by the three intentional synthetic findings.

## Build the five reviewed assets for GitHub Release upload

Build from a clean checkout of the final commit. `MANIFEST.in` includes
`.github`, so any workflow change requires rebuilding and re-auditing the
sdist; never reuse an older source archive.

Use the fixed public timestamp and pinned build tools. On macOS or Linux:

```bash
export SOURCE_DATE_EPOCH=946684800
python3 -m venv .venv
. .venv/bin/activate
python -m pip install "build==1.3.0" "setuptools==77.0.3" "wheel==0.46.2"
python -m build --no-isolation
python scripts/canonicalize_sdist.py --self-test
python scripts/canonicalize_sdist.py --dist-dir dist --output-dir canonical-dist --source-date-epoch 946684800
```

On Windows PowerShell:

```powershell
$env:SOURCE_DATE_EPOCH = "946684800"
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install "build==1.3.0" "setuptools==77.0.3" "wheel==0.46.2"
.\.venv\Scripts\python.exe -m build --no-isolation
.\.venv\Scripts\python.exe scripts\canonicalize_sdist.py --self-test
.\.venv\Scripts\python.exe scripts\canonicalize_sdist.py --dist-dir dist --output-dir canonical-dist --source-date-epoch 946684800
```

Record the three build-tool versions. `--no-isolation` prevents the frontend
from silently creating another environment with unrecorded backend versions.
The canonicalizer fails closed on links, special files, duplicate or unsafe
paths, and oversized input. It sets uid and gid to zero, removes local owner
and gzip metadata, fixes times and modes, and verifies unchanged file content.

Build twice and compare the canonical sdist hashes. Safely unpack the canonical
sdist, run its bundled `privacy_audit.py --sdist` and self-test, inspect the
member list, and install the wheel offline with `--no-index --no-deps` in a
fresh environment. Smoke-test both `chat-archive-guard --version` and
`python -m chat_archive_guard --version` outside the checkout.

Prepare exactly these five uploaded GitHub Release assets. GitHub may also show
automatically generated source-code downloads; those are not uploaded assets and
are outside this five-uploaded-asset allowlist:

- `SOURCE_COMMIT`: the lowercase 40-character commit ID followed by one
  newline
- `SHA256SUMS`: exactly one SHA-256 row each for the SBOM, wheel, and
  canonical sdist
- `chat_archive_guard-0.1.0.cdx.json`: reviewed CycloneDX 1.6 SBOM
- `chat_archive_guard-0.1.0-py3-none-any.whl`: reviewed wheel
- `chat_archive_guard-0.1.0.tar.gz`: reviewed canonical sdist from
  `canonical-dist`, never the raw archive from `dist`

Keep artifact hashes outside the Markdown release notes: record them only in
`SHA256SUMS` and the private release audit record. Do not upload chat archives,
chat databases, messages, credentials, personal data, local paths, logs, build
caches, or private test output.

## Publish and approve

1. Create annotated tag `v0.1.0` at the reviewed commit on `main`.
2. Create a draft GitHub Release for that exact tag, upload the five assets
   above, and upload no other assets. Review the release text and asset names,
   sizes, checksums, source commit, SBOM identity, and CI evidence.
3. Publish the GitHub Release as a stable release, not a prerelease. The
   `release.published` event starts `.github/workflows/publish-pypi.yml`.
4. Wait for `verify` to finish. It independently enforces tag/version/main
   ancestry, the exact five-uploaded-asset allowlist, source identity and hashes,
   SBOM identity, source privacy and self-tests, canonical sdist identity,
   unpacked-sdist privacy, and offline wheel and CLI behavior.
5. Inspect the `verify` result and uploaded workflow artifact. Only after it
   is green should the required reviewer approve deployment to the `pypi`
   environment. PyPI receives only the wheel and canonical sdist.
6. Verify the public PyPI project version, filenames, metadata, hashes, and
   provenance attestations against the reviewed GitHub Release. A provenance
   attestation does not replace the separately reviewed CycloneDX SBOM.

## Partial failure policy

The publisher uses `skip-existing: false`; it must never silently treat an
already present file as a successful retry. If PyPI accepts only one of the two
distributions, freeze the release workflow and do not rebuild, replace, retag,
or blindly rerun it. Compare PyPI's JSON metadata and file hash with the exact
reviewed GitHub Release asset, determine which file is missing, and obtain a
separate maintainer approval for a narrowly scoped recovery using the unchanged
missing artifact. If uploaded content is wrong or unsafe, use PyPI's supported
yank or incident process after separate approval; published files are
immutable.
