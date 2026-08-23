#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fail closed on publication-time privacy, provenance, and packaging hazards."""

from __future__ import annotations

import argparse
import ast
import collections
import errno
import hashlib
import json
import os
import re
import stat
import tempfile
from pathlib import Path
from typing import Counter, Dict, Iterator, Optional, Sequence, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_LICENSE_SHA256 = "c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4"
MAX_FILE_BYTES = 1_048_576
SDIST_EGG_INFO = "src/chat_archive_guard.egg-info"
SKIP_DIRS = frozenset((".git",))
RESIDUE_DIRS = frozenset(
    (
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "__pycache__",
        "build",
        "dist",
    )
)
TEXT_SUFFIXES = frozenset(
    (
        "",
        ".cfg",
        ".in",
        ".ini",
        ".json",
        ".md",
        ".py",
        ".rst",
        ".toml",
        ".txt",
        ".yaml",
        ".yml",
    )
)
TEXT_NAMES = frozenset((".gitignore", "LICENSE", "MANIFEST.in", "PKG-INFO"))
PERSISTENT_DATA_SUFFIXES = frozenset(
    (
        ".avro",
        ".csv",
        ".db",
        ".docx",
        ".eml",
        ".gif",
        ".gz",
        ".har",
        ".jpeg",
        ".jpg",
        ".jsonl",
        ".key",
        ".log",
        ".mbox",
        ".msg",
        ".ndjson",
        ".p12",
        ".parquet",
        ".pcap",
        ".pdf",
        ".pem",
        ".pfx",
        ".png",
        ".ppt",
        ".pptx",
        ".pyc",
        ".sqlite",
        ".sqlite3",
        ".tsv",
        ".webp",
        ".whl",
        ".zip",
    )
)
FORBIDDEN_NAMES = frozenset((".DS_Store", ".env", "credentials.json", "secrets.json"))
REQUIRED_FILES = (
    ".github/CODEOWNERS",
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/ISSUE_TEMPLATE/security_coordination.yml",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/dependabot.yml",
    ".github/workflows/ci.yml",
    "CHANGELOG.md",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "MANIFEST.in",
    "PROVENANCE.md",
    "README.md",
    "RELEASING.md",
    "SECURITY.md",
    "SUPPORT.md",
    "THREAT_MODEL.md",
    "pyproject.toml",
    "scripts/privacy_audit.py",
    "src/chat_archive_guard/__init__.py",
    "src/chat_archive_guard/__main__.py",
    "src/chat_archive_guard/cli.py",
    "src/chat_archive_guard/detectors.py",
    "src/chat_archive_guard/model.py",
    "src/chat_archive_guard/scanner.py",
)
NETWORK_IMPORTS = frozenset(
    (
        "aiohttp",
        "boto3",
        "ftplib",
        "http",
        "httpx",
        "paramiko",
        "requests",
        "sentry_sdk",
        "smtplib",
        "socket",
        "subprocess",
        "telnetlib",
        "urllib",
        "urllib3",
        "websocket",
        "websockets",
        "xmlrpc",
    )
)


def _joined(*parts: str) -> str:
    """Keep audit canaries from matching this script's own source."""

    return "".join(parts)


CONTENT_PATTERNS: Sequence[Tuple[str, re.Pattern]] = (
    (
        "source.absolute_host_path",
        re.compile(
            _joined(
                r"(?:/(?:",
                "root",
                r"|",
                "Users",
                r"|",
                "home",
                r")/|[A-Za-z]:\\",
                "Users",
                r"\\)",
            )
        ),
    ),
    (
        "source.email_literal",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    ),
    (
        "source.phone_literal",
        re.compile(r"(?<![A-Za-z0-9])(?:\+?\d[ -]?){10,15}(?![A-Za-z0-9])"),
    ),
    (
        "source.ipv4_literal",
        re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])"),
    ),
    (
        "source.provider_key_literal",
        re.compile(
            _joined(
                r"(?<![A-Za-z0-9])(?:",
                "s",
                r"k-[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{12,}|gh[pousr]_[A-Za-z0-9]{20,})(?![A-Za-z0-9])",
            )
        ),
    ),
    (
        "source.private_key_literal",
        re.compile(
            _joined(
                r"-----BEGIN ",
                r"(?:RSA |EC |OPENSSH )?",
                "PRIVATE KEY",
                r"-----",
            )
        ),
    ),
    (
        "source.credential_assignment",
        re.compile(
            r"(?i)\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|password|passwd)\b"
            r"\s*[:=]\s*['\"][^'\"\s]{8,}['\"]"
        ),
    ),
)


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return "."


def _is_link_like(path: Path, metadata: Optional[os.stat_result] = None) -> bool:
    """Recognize POSIX symlinks and Windows reparse-point links/junctions."""

    observed = metadata if metadata is not None else path.lstat()
    if stat.S_ISLNK(observed.st_mode):
        return True
    attributes = int(getattr(observed, "st_file_attributes", 0))
    reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
    return bool(reparse_flag and attributes & reparse_flag)


def _iter_files(
    root: Path,
    findings: Counter[Tuple[str, str]],
    allow_sdist_egg_info: bool = False,
) -> Iterator[Path]:
    def on_walk_error(error: OSError) -> None:
        raw = getattr(error, "filename", None)
        path = Path(raw) if isinstance(raw, str) else root
        findings[(_relative(path, root), "scan.walk_error")] += 1

    for directory, names, files in os.walk(
        str(root), topdown=True, followlinks=False, onerror=on_walk_error
    ):
        base = Path(directory)
        kept = []
        for name in sorted(names):
            candidate = base / name
            relative = _relative(candidate, root)
            try:
                metadata = candidate.lstat()
                is_symlink = _is_link_like(candidate, metadata)
            except OSError:
                findings[(relative, "scan.metadata_error")] += 1
                continue
            if is_symlink:
                findings[(relative, "artifact.symlink")] += 1
            elif name.endswith(".egg-info"):
                if allow_sdist_egg_info and relative == SDIST_EGG_INFO:
                    kept.append(name)
                else:
                    findings[(relative, "artifact.generated_directory")] += 1
            elif name in RESIDUE_DIRS:
                findings[(relative, "artifact.generated_directory")] += 1
            elif name not in SKIP_DIRS:
                kept.append(name)
        names[:] = kept
        for name in sorted(files):
            yield base / name


def _metadata_checks(root: Path, findings: Counter[Tuple[str, str]]) -> None:
    for relative in REQUIRED_FILES:
        if not (root / relative).is_file():
            findings[(relative, "release.required_file_missing")] += 1

    try:
        license_bytes = (root / "LICENSE").read_bytes().replace(b"\r\n", b"\n")
    except OSError:
        license_bytes = b""
    if hashlib.sha256(license_bytes).hexdigest() != EXPECTED_LICENSE_SHA256:
        findings[("LICENSE", "license.apache_2_0_mismatch")] += 1

    try:
        metadata = (root / "pyproject.toml").read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return
    metadata_checks = (
        (r'(?m)^name\s*=\s*"chat-archive-guard"\s*$', "metadata.project_name_mismatch"),
        (r'(?m)^license\s*=\s*"Apache-2\.0"\s*$', "metadata.license_expression_missing"),
        (r'(?m)^license-files\s*=\s*\[\s*"LICENSE"\s*\]\s*$', "metadata.license_file_missing"),
        (r'(?m)^requires-python\s*=\s*">=3\.11"\s*$', "metadata.python_requirement_mismatch"),
        (r'(?m)^dependencies\s*=\s*\[\s*\]\s*$', "metadata.runtime_dependencies_present"),
        (r'(?m)^\s*"archive-integrity",\s*$', "metadata.archive_integrity_keyword_missing"),
        (r'(?m)^\s*"chat-export",\s*$', "metadata.chat_export_keyword_missing"),
        (r'(?m)^\s*"log-scanning",\s*$', "metadata.log_scanning_keyword_missing"),
        (r'(?m)^\s*"offline-scanner",\s*$', "metadata.offline_scanner_keyword_missing"),
        (r'(?m)^\s*"pii-detection",\s*$', "metadata.pii_detection_keyword_missing"),
        (r'(?m)^\s*"privacy",\s*$', "metadata.privacy_keyword_missing"),
        (r'(?m)^\s*"privacy-audit",\s*$', "metadata.privacy_audit_keyword_missing"),
        (r'(?m)^\s*"read-only",\s*$', "metadata.read_only_keyword_missing"),
        (r'(?m)^\s*"security",\s*$', "metadata.security_keyword_missing"),
        (r'(?m)^\s*"secret-scanning",\s*$', "metadata.secret_scanning_keyword_missing"),
        (r'(?m)^\s*"sqlite",\s*$', "metadata.sqlite_keyword_missing"),
        (r'(?m)^\s*"sqlite-fts",\s*$', "metadata.sqlite_fts_keyword_missing"),
        (r'(?m)^\s*"wal",\s*$', "metadata.wal_keyword_missing"),
        (r'(?m)^\s*"Operating System :: OS Independent",\s*$', "metadata.os_classifier_missing"),
        (r'(?m)^Homepage\s*=\s*"https://github\.com/MaxHu-xuan/chat-archive-guard"\s*$', "metadata.homepage_missing"),
        (r'(?m)^Repository\s*=\s*"https://github\.com/MaxHu-xuan/chat-archive-guard"\s*$', "metadata.repository_missing"),
        (r'(?m)^Issues\s*=\s*"https://github\.com/MaxHu-xuan/chat-archive-guard/issues"\s*$', "metadata.issues_missing"),
        (r'(?m)^chat-archive-guard\s*=\s*"chat_archive_guard\.cli:main"\s*$', "metadata.console_script_mismatch"),
        (r'(?m)^package-dir\s*=\s*\{\s*""\s*=\s*"src"\s*\}\s*$', "metadata.package_directory_mismatch"),
        (r"setuptools>=77\.0\.3", "metadata.build_backend_too_old"),
    )
    for pattern, category in metadata_checks:
        if not re.search(pattern, metadata):
            findings[("pyproject.toml", category)] += 1

    try:
        readme = (root / "README.md").read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        readme = ""
    if "Python 3.11 or newer is required." not in readme:
        findings[("README.md", "metadata.python_documentation_mismatch")] += 1
    for phrase, category in (
        ("ChatArchiveGuard（聊天归档守护）", "metadata.bilingual_name_missing"),
        ("## 中文说明", "metadata.chinese_overview_missing"),
        ("## English overview", "metadata.english_overview_missing"),
        ("### 用户价值", "metadata.chinese_value_missing"),
        ("### 适用场景", "metadata.chinese_use_cases_missing"),
        ("### 完整性检查", "metadata.chinese_integrity_checks_missing"),
        ("### 隐私与安全", "metadata.chinese_privacy_section_missing"),
        ("### 快速开始", "metadata.chinese_quick_start_missing"),
        ("### 使用局限", "metadata.chinese_limitations_missing"),
        ("### User value", "metadata.english_value_missing"),
        ("### Use cases", "metadata.english_use_cases_missing"),
        ("### Integrity checks", "metadata.english_integrity_checks_missing"),
        ("### Privacy and security", "metadata.english_privacy_section_missing"),
        ("### Quick start", "metadata.english_quick_start_missing"),
        ("### Limitations", "metadata.english_limitations_missing"),
        ("## 中文技术参考", "metadata.chinese_technical_reference_missing"),
        ("## English technical reference", "metadata.english_technical_reference_missing"),
        ("### 工作原理", "metadata.chinese_architecture_summary_missing"),
        ("### How it works", "metadata.english_architecture_summary_missing"),
        ("### 常见问题", "metadata.chinese_faq_missing"),
        ("### FAQ", "metadata.english_faq_missing"),
        ("### Platform behavior", "metadata.platform_documentation_missing"),
        ("format.invalid_json", "metadata.verifiable_example_missing"),
        ("--summary-only", "metadata.summary_only_documentation_missing"),
        ("message completeness", "metadata.message_completeness_boundary_missing"),
        ("source attribution", "metadata.source_attribution_boundary_missing"),
        ("rotated logs", "metadata.rotated_logs_boundary_missing"),
    ):
        if phrase not in readme:
            findings[("README.md", category)] += 1

    try:
        codeowners = (root / ".github" / "CODEOWNERS").read_text(
            encoding="utf-8"
        )
    except (OSError, UnicodeError):
        codeowners = ""
    if codeowners.strip() != "* @MaxHu-xuan":
        findings[(".github/CODEOWNERS", "metadata.codeowners_mismatch")] += 1

    try:
        manifest_lines = set(
            (root / "MANIFEST.in").read_text(encoding="utf-8").splitlines()
        )
    except (OSError, UnicodeError):
        return
    for entry in (
        "include CHANGELOG.md",
        "include CODE_OF_CONDUCT.md",
        "include LICENSE",
        "include RELEASING.md",
        "include SECURITY.md",
        "include SUPPORT.md",
        "include scripts/privacy_audit.py",
        "recursive-include .github *",
    ):
        if entry not in manifest_lines:
            findings[("MANIFEST.in", "metadata.sdist_entry_missing")] += 1


def _report(
    findings: Counter[Tuple[str, str]], files_scanned: int
) -> Dict[str, object]:
    rows = [
        {"path": path, "category": category, "count": count}
        for (path, category), count in sorted(findings.items())
    ]
    return {
        "schema": "chat-archive-guard-privacy-audit-v1",
        "ok": not rows,
        "files_scanned": files_scanned,
        "finding_count": sum(int(row["count"]) for row in rows),
        "findings": rows,
    }


def audit(
    root: Path,
    validate_release: bool = True,
    sdist: bool = False,
) -> Dict[str, object]:
    findings: Counter[Tuple[str, str]] = collections.Counter()
    files_scanned = 0
    try:
        root_metadata = root.lstat()
        if _is_link_like(root, root_metadata) or not stat.S_ISDIR(root_metadata.st_mode):
            findings[(".", "scan.invalid_root")] += 1
            return _report(findings, files_scanned)
        root = root.resolve(strict=True)
    except OSError:
        findings[(".", "scan.invalid_root")] += 1
        return _report(findings, files_scanned)

    if validate_release:
        _metadata_checks(root, findings)

    for path in _iter_files(root, findings, allow_sdist_egg_info=sdist):
        relative = _relative(path, root)
        try:
            metadata = path.lstat()
        except OSError:
            findings[(relative, "scan.metadata_error")] += 1
            continue
        if _is_link_like(path, metadata):
            findings[(relative, "artifact.symlink")] += 1
            continue
        if not stat.S_ISREG(metadata.st_mode):
            findings[(relative, "artifact.non_regular")] += 1
            continue
        if metadata.st_nlink != 1:
            findings[(relative, "artifact.hardlink")] += 1
        files_scanned += 1
        if path.name in FORBIDDEN_NAMES:
            findings[(relative, "artifact.forbidden_name")] += 1
        if path.suffix.lower() in PERSISTENT_DATA_SUFFIXES:
            findings[(relative, "artifact.persistent_fixture")] += 1
            continue
        if metadata.st_size > MAX_FILE_BYTES:
            findings[(relative, "artifact.oversized")] += 1
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in TEXT_NAMES:
            findings[(relative, "artifact.binary_or_unknown")] += 1
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="strict")
        except (OSError, UnicodeError):
            findings[(relative, "scan.text_error")] += 1
            continue
        for category, pattern in CONTENT_PATTERNS:
            count = sum(1 for _ in pattern.finditer(text))
            if count:
                findings[(relative, category)] += count
        if path.suffix.lower() == ".py":
            if "# SPDX-License-Identifier: Apache-2.0" not in text.splitlines()[:5]:
                findings[(relative, "license.spdx_missing")] += 1
            try:
                tree = ast.parse(text)
            except SyntaxError:
                findings[(relative, "source.syntax_error")] += 1
                continue
            imports = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.add(node.module.split(".")[0])
            for name in imports & NETWORK_IMPORTS:
                findings[(relative, "source.network_or_process_import")] += 1
    return _report(findings, files_scanned)


def _read_small_regular_file(path: Path) -> Optional[bytes]:
    """Read bounded context evidence without following links."""

    try:
        metadata = path.lstat()
        if (
            _is_link_like(path, metadata)
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or metadata.st_size > MAX_FILE_BYTES
        ):
            return None
        with path.open("rb") as handle:
            payload = handle.read(MAX_FILE_BYTES + 1)
    except OSError:
        return None
    return payload if len(payload) <= MAX_FILE_BYTES else None


def _is_own_unpacked_sdist(root: Path) -> bool:
    """Strictly identify this project's standard unpacked source archive."""

    try:
        root_metadata = root.lstat()
        if _is_link_like(root, root_metadata) or not stat.S_ISDIR(root_metadata.st_mode):
            return False
    except OSError:
        return False

    top_metadata = _read_small_regular_file(root / "PKG-INFO")
    egg_metadata = _read_small_regular_file(root / SDIST_EGG_INFO / "PKG-INFO")
    project_metadata = _read_small_regular_file(root / "pyproject.toml")
    generated_config = _read_small_regular_file(root / "setup.cfg")
    manifest = _read_small_regular_file(root / SDIST_EGG_INFO / "SOURCES.txt")
    if (
        top_metadata is None
        or top_metadata != egg_metadata
        or project_metadata is None
        or generated_config is None
        or manifest is None
    ):
        return False

    try:
        package_text = top_metadata.decode("utf-8", errors="strict")
        project_text = project_metadata.decode("utf-8", errors="strict")
        manifest_entries = set(manifest.decode("utf-8", errors="strict").splitlines())
    except UnicodeError:
        return False

    version_match = re.search(
        r'(?m)^version\s*=\s*"([^"\r\n]+)"\s*$', project_text
    )
    if version_match is None:
        return False
    package_headers = {
        key: value.strip()
        for line in package_text.splitlines()
        if ":" in line
        for key, value in (line.split(":", 1),)
    }
    required_manifest_entries = {
        ".github/CODEOWNERS",
        ".github/ISSUE_TEMPLATE/bug_report.yml",
        ".github/ISSUE_TEMPLATE/config.yml",
        ".github/ISSUE_TEMPLATE/feature_request.yml",
        ".github/ISSUE_TEMPLATE/security_coordination.yml",
        ".github/PULL_REQUEST_TEMPLATE.md",
        "CHANGELOG.md",
        "CODE_OF_CONDUCT.md",
        "RELEASING.md",
        "SECURITY.md",
        "SUPPORT.md",
        "pyproject.toml",
        "scripts/privacy_audit.py",
        "src/chat_archive_guard.egg-info/PKG-INFO",
        "src/chat_archive_guard.egg-info/SOURCES.txt",
        "tests/test_chat_archive_guard.py",
    }
    return (
        package_headers.get("Name") == "chat-archive-guard"
        and package_headers.get("Version") == version_match.group(1)
        and required_manifest_entries.issubset(manifest_entries)
    )


def self_test(project_root: Path = PROJECT_ROOT, sdist: bool = False) -> bool:
    effective_sdist = sdist or _is_own_unpacked_sdist(project_root)
    if not bool(audit(project_root, sdist=effective_sdist)["ok"]):
        return False
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        values = (
            "/ho" + "me/" + "sample-user/notes",
            "person" + chr(64) + "example.invalid",
            "139" + "\u0660" * 4 + "\u0661" * 4,
            "192" + ".0.2.1",
            "s" + "k-" + "A" * 24,
            "-----BEGIN " + "PRIVATE KEY-----",
            "pass" + "word = 'synthetic-value'",
        )
        source_lines = ["# SPDX-License-Identifier: Apache-2.0"]
        source_lines.extend("# " + value for value in values[:-1])
        source_lines.append(values[-1])
        source_lines.append("import " + "socket")
        (root / "sample.py").write_text("\n".join(source_lines), encoding="utf-8")
        (root / "fixture.db").write_bytes(b"synthetic")
        (root / ".env").write_text("synthetic", encoding="utf-8")
        (root / "__pycache__").mkdir()

        report = audit(root, validate_release=False)
        categories = {str(row["category"]) for row in report["findings"]}
        expected = {
            "artifact.forbidden_name",
            "artifact.generated_directory",
            "artifact.persistent_fixture",
            "source.absolute_host_path",
            "source.credential_assignment",
            "source.email_literal",
            "source.ipv4_literal",
            "source.network_or_process_import",
            "source.phone_literal",
            "source.private_key_literal",
            "source.provider_key_literal",
        }
        encoded = json.dumps(report, sort_keys=True, separators=(",", ":"))
        content_checks_ok = expected.issubset(categories) and not any(
            value in encoded for value in values
        )
    if not content_checks_ok:
        return False

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        allowed = root / SDIST_EGG_INFO
        allowed.mkdir(parents=True)
        metadata = allowed / "PKG-INFO"
        metadata.write_text(
            "Metadata-Version: 2.4\nName: chat-archive-guard\nVersion: 0.1.0\n",
            encoding="utf-8",
        )

        source_report = audit(root, validate_release=False)
        source_generated = {
            str(row["path"])
            for row in source_report["findings"]
            if row["category"] == "artifact.generated_directory"
        }
        if SDIST_EGG_INFO not in source_generated:
            return False

        allowed_report = audit(root, validate_release=False, sdist=True)
        if not bool(allowed_report["ok"]):
            return False

        canary = "s" + "k-" + "Z" * 24
        sources = allowed / "SOURCES.txt"
        sources.write_text(canary + "\n", encoding="utf-8")
        scanned_report = audit(root, validate_release=False, sdist=True)
        scanned_categories = {
            str(row["category"]) for row in scanned_report["findings"]
        }
        scanned_encoded = json.dumps(
            scanned_report, sort_keys=True, separators=(",", ":")
        )
        if (
            "source.provider_key_literal" not in scanned_categories
            or canary in scanned_encoded
        ):
            return False
        sources.write_text("README.md\n", encoding="utf-8")

        impostor = root / "src" / "lookalike.egg-info"
        misplaced = root / "chat_archive_guard.egg-info"
        impostor.mkdir()
        misplaced.mkdir()
        (impostor / "PKG-INFO").write_text("synthetic\n", encoding="utf-8")
        (misplaced / "PKG-INFO").write_text("synthetic\n", encoding="utf-8")

        rejected_report = audit(root, validate_release=False, sdist=True)
        rejected_generated = {
            str(row["path"])
            for row in rejected_report["findings"]
            if row["category"] == "artifact.generated_directory"
        }
        walk_root = root / "walk-root"
        walk_root.mkdir()
        walk_root = walk_root.resolve(strict=True)
        original_walk = os.walk

        def denied_walk(*args, **kwargs):
            del args
            onerror = kwargs.get("onerror")
            if onerror is not None:
                onerror(
                    OSError(
                        errno.EACCES,
                        "synthetic directory error",
                        str(walk_root / "blocked"),
                    )
                )
            return iter(())

        os.walk = denied_walk
        try:
            walk_report = audit(walk_root, validate_release=False)
        finally:
            os.walk = original_walk
        walk_findings = {
            (str(row["path"]), str(row["category"]))
            for row in walk_report["findings"]
        }
        return (
            not bool(rejected_report["ok"])
            and SDIST_EGG_INFO not in rejected_generated
            and {
                "src/lookalike.egg-info",
                "chat_archive_guard.egg-info",
            }.issubset(rejected_generated)
            and not bool(walk_report["ok"])
            and ("blocked", "scan.walk_error") in walk_findings
        )


class _SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise ValueError("invalid arguments")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _SafeArgumentParser(
        description="Audit a release tree without echoing matched values"
    )
    parser.add_argument("root", nargs="?", default=str(PROJECT_ROOT))
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument(
        "--sdist",
        action="store_true",
        help="allow and inspect only src/chat_archive_guard.egg-info",
    )
    try:
        args = parser.parse_args(argv)
        if args.self_test:
            ok = self_test(Path(args.root), sdist=args.sdist)
            report = {
                "ok": ok,
                "code": "ok" if ok else "self_test_failed",
                "count": 0 if ok else 1,
            }
        else:
            report = audit(Path(args.root), sdist=args.sdist)
    except (OSError, UnicodeError, ValueError):
        report = {
            "schema": "chat-archive-guard-privacy-audit-v1",
            "ok": False,
            "files_scanned": 0,
            "finding_count": 1,
            "findings": [
                {"path": ".", "category": "scan.invalid_arguments", "count": 1}
            ],
        }
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0 if bool(report["ok"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
