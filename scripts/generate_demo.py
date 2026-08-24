#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Create a deterministic, entirely synthetic ChatArchiveGuard demo."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import stat
import tempfile
from pathlib import Path
from typing import Optional, Sequence, Tuple


JSONL_NAME = "records.jsonl"
SQLITE_NAME = "archive.sqlite"
FIXED_TIME = "2000-01-01T00:00:00Z"


class _UsageError(ValueError):
    pass


class _SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise _UsageError("invalid command line")


def _assignment_canary() -> str:
    return "".join(("pass", "word", "=", "DEMO_ONLY_NEVER_VALID_0001"))


def _provider_canary() -> str:
    return "".join(("s", "k", "-", "DEMO_ONLY_NEVER_VALID_0002"))


def _chmod_private(path: Path, mode: int) -> None:
    if os.name == "posix":
        path.chmod(mode)


def _jsonl_payload() -> bytes:
    rows = (
        {
            "id": "demo-001",
            "timestamp": FIXED_TIME,
            "body": "Synthetic demo record; not a real conversation.",
        },
        {
            "id": "demo-002",
            "timestamp": FIXED_TIME,
            "body": _assignment_canary(),
        },
    )
    lines = [
        json.dumps(row, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        for row in rows
    ]
    lines.append('{"body":"Synthetic malformed demo record"')
    return ("\n".join(lines) + "\n").encode("utf-8")


def _write_jsonl(path: Path) -> None:
    descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        payload = _jsonl_payload()
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(payload)
            handle.flush()
    finally:
        os.close(descriptor)
    _chmod_private(path, 0o600)


def _write_sqlite(path: Path) -> None:
    with tempfile.TemporaryDirectory(
        prefix=".chat-archive-guard-demo-", dir=str(path.parent)
    ) as directory:
        workspace = Path(directory)
        _chmod_private(workspace, 0o700)
        temporary_descriptor, temporary_name = tempfile.mkstemp(
            prefix="archive-", suffix=".sqlite", dir=str(workspace)
        )
        os.close(temporary_descriptor)
        temporary_path = Path(temporary_name)
        _chmod_private(temporary_path, 0o600)

        connection = sqlite3.connect(temporary_path)
        try:
            connection.execute("PRAGMA page_size = 4096")
            connection.execute("PRAGMA journal_mode = DELETE")
            connection.execute("PRAGMA user_version = 1")
            connection.execute(
                "CREATE TABLE messages ("
                "id TEXT PRIMARY KEY, created_at TEXT NOT NULL, body TEXT NOT NULL)"
            )
            connection.executemany(
                "INSERT INTO messages (id, created_at, body) VALUES (?, ?, ?)",
                (
                    (
                        "demo-101",
                        FIXED_TIME,
                        "Synthetic SQLite record; not a real conversation.",
                    ),
                    ("demo-102", FIXED_TIME, _provider_canary()),
                ),
            )
            connection.commit()
            connection.execute("VACUUM")
        finally:
            connection.close()

        metadata = temporary_path.lstat()
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_ISLNK(metadata.st_mode)
            or metadata.st_nlink != 1
        ):
            raise OSError("temporary database is not a private regular file")

        binary_flag = int(getattr(os, "O_BINARY", 0))
        source_flags = os.O_RDONLY | binary_flag
        no_follow = getattr(os, "O_NOFOLLOW", None)
        if isinstance(no_follow, int) and no_follow:
            source_flags |= no_follow
        source_descriptor = os.open(str(temporary_path), source_flags)
        try:
            destination_descriptor = os.open(
                str(path),
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | binary_flag,
                0o600,
            )
            try:
                if os.name == "posix":
                    os.fchmod(destination_descriptor, 0o600)
                while True:
                    chunk = os.read(source_descriptor, 1024 * 1024)
                    if not chunk:
                        break
                    offset = 0
                    while offset < len(chunk):
                        written = os.write(destination_descriptor, chunk[offset:])
                        if written <= 0:
                            raise OSError("database copy made no progress")
                        offset += written
                os.fsync(destination_descriptor)
            finally:
                os.close(destination_descriptor)
        finally:
            os.close(source_descriptor)


def generate_demo(output_directory: Path) -> Tuple[Path, Path]:
    """Create a new private directory containing two deterministic demo files."""

    output = Path(output_directory)
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    metadata = output.lstat()
    if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise OSError("output is not a private directory")
    _chmod_private(output, 0o700)

    jsonl_path = output / JSONL_NAME
    sqlite_path = output / SQLITE_NAME
    _write_jsonl(jsonl_path)
    _write_sqlite(sqlite_path)
    return jsonl_path, sqlite_path


def _logical_sqlite_rows(path: Path) -> Tuple[Tuple[str, str, str], ...]:
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            "SELECT id, created_at, body FROM messages ORDER BY id"
        ).fetchall()
    finally:
        connection.close()
    return tuple((str(row[0]), str(row[1]), str(row[2])) for row in rows)


def self_test() -> bool:
    with tempfile.TemporaryDirectory() as directory:
        parent = Path(directory)
        first_jsonl, first_sqlite = generate_demo(parent / "first")
        second_jsonl, second_sqlite = generate_demo(parent / "second")
        first_names = sorted(path.name for path in first_jsonl.parent.iterdir())
        second_names = sorted(path.name for path in second_jsonl.parent.iterdir())
        return (
            first_names == [SQLITE_NAME, JSONL_NAME]
            and first_names == second_names
            and first_jsonl.read_bytes() == second_jsonl.read_bytes()
            and _logical_sqlite_rows(first_sqlite)
            == _logical_sqlite_rows(second_sqlite)
        )


def build_parser() -> argparse.ArgumentParser:
    parser = _SafeArgumentParser(
        prog="generate_demo.py",
        description="Create two entirely synthetic ChatArchiveGuard demo files.",
        allow_abbrev=False,
    )
    parser.add_argument("output", nargs="?", help="new output directory")
    parser.add_argument("--self-test", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        if args.self_test:
            if args.output is not None:
                raise _UsageError("invalid command line")
            ok = self_test()
            print(f"synthetic demo self-test: {'PASS' if ok else 'FAIL'}")
            return 0 if ok else 1
        if args.output is None:
            raise _UsageError("invalid command line")
        generate_demo(Path(args.output))
    except _UsageError:
        print("synthetic demo: FAIL reason=invalid_arguments")
        return 2
    except (OSError, RuntimeError, sqlite3.Error, UnicodeError, ValueError):
        print("synthetic demo: FAIL reason=generation_error")
        return 1
    print("synthetic demo: PASS files=2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
