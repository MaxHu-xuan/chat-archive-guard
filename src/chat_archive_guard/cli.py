# SPDX-License-Identifier: Apache-2.0
"""Command-line interface with value-free output."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

from . import __version__
from .scanner import (
    DEFAULT_MAX_FILES,
    DEFAULT_MAX_FINDINGS,
    ScanConfig,
    scan_tree,
)


class _UsageError(ValueError):
    pass


class _SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise _UsageError("invalid command line")


def build_parser() -> argparse.ArgumentParser:
    parser = _SafeArgumentParser(
        prog="chat-archive-guard",
        description="Scan local chat archives without emitting matched content.",
    )
    parser.add_argument("root", nargs="?", default=".", help="file or directory to scan")
    parser.add_argument("--json", action="store_true", help="emit stable JSON")
    parser.add_argument("--max-file-mib", type=int, default=16, help="maximum text file size")
    parser.add_argument("--max-sqlite-rows", type=int, default=100_000, help="maximum rows per database")
    parser.add_argument("--max-sqlite-value-kib", type=int, default=1024, help="maximum bytes inspected per SQLite value")
    parser.add_argument(
        "--max-files",
        type=int,
        default=DEFAULT_MAX_FILES,
        help="maximum regular files inspected",
    )
    parser.add_argument(
        "--max-findings",
        type=int,
        default=DEFAULT_MAX_FINDINGS,
        help="maximum finding occurrences retained",
    )
    parser.add_argument("--version", action="version", version=__version__)
    return parser


def _fatal(as_json: bool) -> int:
    if as_json:
        payload = {
            "schema_version": 1,
            "ok": False,
            "complete": False,
            "truncated": False,
            "root": ".",
            "summary": {"files_seen": 0, "files_scanned": 0, "finding_count": 1, "categories": {"scan.root_unavailable": 1}},
            "findings": [{"path": "[root]", "category": "scan.root_unavailable", "count": 1}],
        }
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    else:
        print("FAIL scan.root_unavailable count=1")
    return 2


def main(argv: Optional[Sequence[str]] = None) -> int:
    raw_args = list(argv) if argv is not None else sys.argv[1:]
    wants_json = "--json" in raw_args
    try:
        args = build_parser().parse_args(raw_args)
        config = ScanConfig(
            root=Path(args.root),
            max_file_bytes=args.max_file_mib * 1024 * 1024,
            max_sqlite_rows=args.max_sqlite_rows,
            max_sqlite_value_bytes=args.max_sqlite_value_kib * 1024,
            max_files=args.max_files,
            max_findings=args.max_findings,
        )
        report = scan_tree(config)
    except (OSError, ValueError, RuntimeError, UnicodeError):
        return _fatal(wants_json)

    if args.json:
        print(json.dumps(report.to_dict(), sort_keys=True, separators=(",", ":")))
    else:
        status = "OK" if report.ok else "FAIL"
        print(
            f"{status} files_seen={report.files_seen} "
            f"files_scanned={report.files_scanned} findings={report.finding_count} "
            f"complete={str(report.complete).lower()} "
            f"truncated={str(report.truncated).lower()}"
        )
        for finding in report.findings:
            safe_path = json.dumps(finding.path, ensure_ascii=True)
            print(f"{safe_path}\t{finding.category}\t{finding.count}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
