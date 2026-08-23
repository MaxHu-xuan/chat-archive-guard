# SPDX-License-Identifier: Apache-2.0
"""Read-only scanners for text, JSON, JSONL, and SQLite archives."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import stat
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Counter as CounterType, Dict, Iterator, List, Optional, Tuple

from .detectors import detect_text
from .model import ScanReport, build_findings


TEXT_SUFFIXES = frozenset({".txt", ".md", ".log", ".csv", ".tsv", ".yaml", ".yml"})
JSON_SUFFIXES = frozenset({".json"})
JSONL_SUFFIXES = frozenset({".jsonl", ".ndjson"})
SQLITE_SUFFIXES = frozenset({".db", ".sqlite", ".sqlite3"})
SQLITE_HEADER = b"SQLite format 3\x00"
DEFAULT_MAX_FILES = 10_000
DEFAULT_MAX_FINDINGS = 10_000
MAX_ALLOWED_FILE_BYTES = 256 * 1024 * 1024
MAX_ALLOWED_SQLITE_ROWS = 1_000_000
MAX_ALLOWED_SQLITE_VALUE_BYTES = 16 * 1024 * 1024
MAX_ALLOWED_FILES = 100_000
MAX_ALLOWED_FINDINGS = 100_000
_POSIX_MODE_SEMANTICS = os.name == "posix"


def _is_link_like(path: Path, metadata: Optional[os.stat_result] = None) -> bool:
    """Recognize POSIX symlinks and Windows reparse-point links/junctions."""

    observed = metadata if metadata is not None else path.lstat()
    if stat.S_ISLNK(observed.st_mode):
        return True
    attributes = int(getattr(observed, "st_file_attributes", 0))
    reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
    return bool(reparse_flag and attributes & reparse_flag)


def _read_only_flags(require_no_follow: bool = False) -> int:
    """Return binary read flags, optionally requiring an atomic no-follow open."""

    flags = os.O_RDONLY | int(getattr(os, "O_BINARY", 0))
    no_follow = getattr(os, "O_NOFOLLOW", None)
    if isinstance(no_follow, int) and no_follow:
        return flags | no_follow
    if require_no_follow:
        raise _SQLiteSidecarUnsafe()
    return flags


@dataclass(frozen=True)
class ScanConfig:
    root: Path
    max_file_bytes: int = 16 * 1024 * 1024
    max_sqlite_rows: int = 100_000
    max_sqlite_value_bytes: int = 1024 * 1024
    max_files: int = DEFAULT_MAX_FILES
    max_findings: int = DEFAULT_MAX_FINDINGS

    def normalized(self) -> "ScanConfig":
        numeric_limits = (
            self.max_file_bytes,
            self.max_sqlite_rows,
            self.max_sqlite_value_bytes,
            self.max_files,
            self.max_findings,
        )
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
            for value in numeric_limits
        ):
            raise ValueError("limits must be positive")
        supported_maxima = (
            MAX_ALLOWED_FILE_BYTES,
            MAX_ALLOWED_SQLITE_ROWS,
            MAX_ALLOWED_SQLITE_VALUE_BYTES,
            MAX_ALLOWED_FILES,
            MAX_ALLOWED_FINDINGS,
        )
        if any(
            value > maximum
            for value, maximum in zip(numeric_limits, supported_maxima)
        ):
            raise ValueError("limits exceed the supported maximum")
        root = _absolute_path_without_symlink(self.root)
        return ScanConfig(
            root=root,
            max_file_bytes=self.max_file_bytes,
            max_sqlite_rows=self.max_sqlite_rows,
            max_sqlite_value_bytes=self.max_sqlite_value_bytes,
            max_files=self.max_files,
            max_findings=self.max_findings,
        )


def _absolute_path_without_symlink(path: Path) -> Path:
    """Return an absolute path only after every supplied component passed lstat."""

    supplied = Path(os.fspath(path))
    absolute = supplied if supplied.is_absolute() else Path.cwd() / supplied
    if ".." in absolute.parts:
        raise ValueError("scan root must not contain parent traversal")
    current = Path(absolute.anchor)
    for component in absolute.parts[1:]:
        current /= component
        metadata = current.lstat()
        if _is_link_like(current, metadata):
            raise ValueError("scan root ancestry must not contain a symlink")
    resolved = absolute.resolve(strict=True)
    if resolved != absolute:
        raise ValueError("scan root resolution changed")
    return absolute


class _Accumulator:
    def __init__(self, root: Path, max_findings: int) -> None:
        self.root = root
        self.counts: CounterType[Tuple[str, str]] = Counter()
        self.files_seen = 0
        self.files_scanned = 0
        self.max_findings = max_findings
        self.retained_finding_count = 0
        self.file_limit_reached = False
        self.finding_limit_reached = False
        self.content_limit_reached = False

    def relative(self, path: Path) -> str:
        try:
            relative = path.relative_to(self.root)
        except ValueError:
            return "[outside-root]"
        value = relative.as_posix()
        return value if value and value != "." else "[root]"

    def add(self, path: Path, category: str, count: int = 1) -> None:
        requested = int(count)
        if requested <= 0:
            return
        remaining = self.max_findings - self.retained_finding_count
        retained = min(requested, max(remaining, 0))
        if retained:
            self.counts[(self.relative(path), category)] += retained
            self.retained_finding_count += retained
        if retained < requested:
            self.finding_limit_reached = True

    def add_detected(self, path: Path, text: str) -> None:
        for category, count in detect_text(text).items():
            self.add(path, category, count)
            if self.finding_limit_reached:
                break

    def add_content_limit(self, path: Path, category: str, count: int = 1) -> None:
        requested = int(count)
        if requested <= 0:
            return
        self.content_limit_reached = True
        self.add(path, category, requested)

    def report(self) -> ScanReport:
        report_counts = Counter(self.counts)
        if self.file_limit_reached:
            report_counts[("[root]", "scan.file_limit")] += 1
        if self.finding_limit_reached:
            report_counts[("[root]", "scan.finding_limit")] += 1
        truncated = (
            self.file_limit_reached
            or self.finding_limit_reached
            or self.content_limit_reached
        )
        return ScanReport(
            files_seen=self.files_seen,
            files_scanned=self.files_scanned,
            findings=build_findings(report_counts),
            complete=not truncated,
            truncated=truncated,
        )


def _iter_paths(root: Path, accumulator: _Accumulator) -> Iterator[Path]:
    root_metadata = root.lstat()
    if stat.S_ISREG(root_metadata.st_mode) and not _is_link_like(root, root_metadata):
        yield root
        return

    def on_walk_error(error: OSError) -> None:
        raw_path = getattr(error, "filename", None)
        accumulator.add(Path(raw_path) if isinstance(raw_path, str) else root, "scan.read_error")

    for dirpath, dirnames, filenames in os.walk(
        str(root), topdown=True, onerror=on_walk_error, followlinks=False
    ):
        current = Path(dirpath)
        kept = []
        for name in sorted(dirnames):
            candidate = current / name
            try:
                metadata = candidate.lstat()
                if _is_link_like(candidate, metadata):
                    accumulator.add(candidate, "scan.symlink_skipped")
                    if accumulator.finding_limit_reached:
                        dirnames[:] = []
                        return
                else:
                    kept.append(name)
            except OSError:
                accumulator.add(candidate, "scan.metadata_error")
                if accumulator.finding_limit_reached:
                    dirnames[:] = []
                    return
        dirnames[:] = kept
        for name in sorted(filenames):
            yield current / name


def _read_regular_file(path: Path, limit: int) -> Optional[bytes]:
    descriptor = os.open(str(path), _read_only_flags())
    try:
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            data = handle.read(limit + 1)
    finally:
        os.close(descriptor)
    if len(data) > limit:
        return None
    return data


def _read_prefix(path: Path, length: int = 64) -> bytes:
    descriptor = os.open(str(path), _read_only_flags())
    try:
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            return handle.read(length)
    finally:
        os.close(descriptor)


def _sqlite_candidate(path: Path, prefix: bytes) -> bool:
    return path.suffix.lower() in SQLITE_SUFFIXES or prefix.startswith(SQLITE_HEADER)


def _scan_text_file(path: Path, data: bytes, kind: str, accumulator: _Accumulator) -> None:
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        accumulator.add(path, "format.invalid_utf8")
        text = data.decode("utf-8", errors="replace")
    accumulator.add_detected(path, text)

    if kind == "json":
        try:
            json.loads(text)
        except (json.JSONDecodeError, RecursionError, ValueError):
            accumulator.add(path, "format.invalid_json")
    elif kind == "jsonl":
        invalid = 0
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                json.loads(line)
            except (json.JSONDecodeError, RecursionError, ValueError):
                invalid += 1
        accumulator.add(path, "format.invalid_jsonl", invalid)


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _value_text(value: object, byte_limit: int) -> Tuple[Optional[str], bool]:
    if isinstance(value, str):
        encoded = value.encode("utf-8", errors="replace")
        if len(encoded) > byte_limit:
            return encoded[:byte_limit].decode("utf-8", errors="ignore"), True
        return value, False
    if isinstance(value, bytes):
        if len(value) > byte_limit:
            return value[:byte_limit].decode("utf-8", errors="ignore"), True
        return value.decode("utf-8", errors="ignore"), False
    return None, False


@dataclass(frozen=True)
class _FileIdentity:
    device: int
    inode: int
    mode: int
    links: int
    size: int
    modified_ns: int
    changed_ns: int

    @classmethod
    def from_stat(cls, metadata: os.stat_result) -> "_FileIdentity":
        return cls(
            device=metadata.st_dev,
            inode=metadata.st_ino,
            mode=metadata.st_mode,
            links=metadata.st_nlink,
            size=metadata.st_size,
            modified_ns=metadata.st_mtime_ns,
            changed_ns=metadata.st_ctime_ns,
        )


class _SQLiteSnapshotChanged(Exception):
    pass


class _SQLiteSidecarUnsafe(Exception):
    pass


class _SQLiteSizeLimit(Exception):
    pass


def _sqlite_source_parts(path: Path, max_bytes: int) -> Dict[str, Tuple[Path, _FileIdentity]]:
    parts: Dict[str, Tuple[Path, _FileIdentity]] = {}
    total_bytes = 0
    for suffix, private_name in (("", "database.sqlite"), ("-wal", "database.sqlite-wal"), ("-shm", "database.sqlite-shm")):
        candidate = Path(str(path) + suffix)
        try:
            metadata = candidate.lstat()
        except FileNotFoundError:
            if not suffix:
                raise _SQLiteSnapshotChanged()
            continue
        except OSError as error:
            raise _SQLiteSnapshotChanged() from error
        if _is_link_like(candidate, metadata) or not stat.S_ISREG(metadata.st_mode):
            raise _SQLiteSidecarUnsafe()
        identity = _FileIdentity.from_stat(metadata)
        total_bytes += identity.size
        if total_bytes > max_bytes:
            raise _SQLiteSizeLimit()
        parts[private_name] = (candidate, identity)
    return parts


def _same_identity(metadata: os.stat_result, expected: _FileIdentity) -> bool:
    return _FileIdentity.from_stat(metadata) == expected


def _copy_sqlite_part(source: Path, destination: Path, expected: _FileIdentity) -> bytes:
    source_descriptor = os.open(str(source), _read_only_flags(require_no_follow=True))
    destination_descriptor: Optional[int] = None
    digest = hashlib.sha256()
    copied = 0
    try:
        if not _same_identity(os.fstat(source_descriptor), expected):
            raise _SQLiteSnapshotChanged()
        destination_descriptor = os.open(
            str(destination), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
        )
        os.fchmod(destination_descriptor, 0o600)
        while copied <= expected.size:
            chunk = os.read(
                source_descriptor,
                min(1024 * 1024, expected.size + 1 - copied),
            )
            if not chunk:
                break
            digest.update(chunk)
            copied += len(chunk)
            if copied > expected.size:
                raise _SQLiteSnapshotChanged()
            view = memoryview(chunk)
            while view:
                written = os.write(destination_descriptor, view)
                if written <= 0:
                    raise OSError("short private snapshot write")
                view = view[written:]
        if copied != expected.size or not _same_identity(os.fstat(source_descriptor), expected):
            raise _SQLiteSnapshotChanged()
        os.fsync(destination_descriptor)
    finally:
        if destination_descriptor is not None:
            os.close(destination_descriptor)
        os.close(source_descriptor)
    return digest.digest()


def _hash_sqlite_part(source: Path, expected: _FileIdentity) -> bytes:
    descriptor = os.open(str(source), _read_only_flags(require_no_follow=True))
    digest = hashlib.sha256()
    observed = 0
    try:
        if not _same_identity(os.fstat(descriptor), expected):
            raise _SQLiteSnapshotChanged()
        while observed <= expected.size:
            chunk = os.read(
                descriptor,
                min(1024 * 1024, expected.size + 1 - observed),
            )
            if not chunk:
                break
            observed += len(chunk)
            if observed > expected.size:
                raise _SQLiteSnapshotChanged()
            digest.update(chunk)
        if observed != expected.size or not _same_identity(os.fstat(descriptor), expected):
            raise _SQLiteSnapshotChanged()
    finally:
        os.close(descriptor)
    return digest.digest()


def _open_sqlite_snapshot(path: Path, max_bytes: int) -> sqlite3.Connection:
    """Open SQLite only after an O_NOFOLLOW copy into a private temporary tree."""

    before = _sqlite_source_parts(path, max_bytes)
    with tempfile.TemporaryDirectory(prefix="chat-archive-guard-") as temporary:
        private_root = Path(temporary)
        os.chmod(private_root, 0o700)
        copied_hashes: Dict[str, bytes] = {}
        for private_name, (source_path, identity) in before.items():
            copied_hashes[private_name] = _copy_sqlite_part(
                source_path, private_root / private_name, identity
            )

        after = _sqlite_source_parts(path, max_bytes)
        if before != after:
            raise _SQLiteSnapshotChanged()
        for private_name, (source_path, identity) in after.items():
            if _hash_sqlite_part(source_path, identity) != copied_hashes[private_name]:
                raise _SQLiteSnapshotChanged()
        if _sqlite_source_parts(path, max_bytes) != before:
            raise _SQLiteSnapshotChanged()

        private_database = private_root / "database.sqlite"
        uri = private_database.as_uri() + "?mode=ro"
        source = sqlite3.connect(uri, uri=True, timeout=2.0)
        target: Optional[sqlite3.Connection] = None
        try:
            source.execute("PRAGMA query_only = ON")
            try:
                source.execute("PRAGMA trusted_schema = OFF")
            except sqlite3.DatabaseError:
                pass
            target = sqlite3.connect(":memory:")
            source.backup(target)
            target.execute("PRAGMA query_only = ON")
            try:
                target.execute("PRAGMA trusted_schema = OFF")
            except sqlite3.DatabaseError:
                pass
            return target
        except BaseException:
            if target is not None:
                target.close()
            raise
        finally:
            source.close()


def _sqlite_table_names(connection: sqlite3.Connection) -> List[str]:
    try:
        rows = connection.execute("PRAGMA table_list").fetchall()
    except sqlite3.Error:
        rows = []
    if rows:
        return sorted(
            row[1]
            for row in rows
            if len(row) >= 3
            and row[0] == "main"
            and isinstance(row[1], str)
            and not row[1].startswith("sqlite_")
            and row[2] in ("table", "virtual")
        )
    fallback = connection.execute(
        "SELECT name, sql FROM sqlite_master "
        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    fts_shadows = set()
    for name, sql in fallback:
        if not isinstance(name, str) or not isinstance(sql, str):
            continue
        normalized_sql = " ".join(sql.lower().split())
        module = ""
        if " using " in normalized_sql:
            module = normalized_sql.split(" using ", 1)[1].split("(", 1)[0]
            module = module.strip().strip("'\"`[]")
        if module in ("fts3", "fts4"):
            fts_shadows.update(
                name + suffix
                for suffix in ("_content", "_segments", "_segdir", "_docsize", "_stat")
            )
        elif module == "fts5":
            fts_shadows.update(
                name + suffix
                for suffix in ("_data", "_idx", "_content", "_docsize", "_config")
            )
    return [
        row[0]
        for row in fallback
        if isinstance(row[0], str) and row[0] not in fts_shadows
    ]


def _scan_sqlite(path: Path, config: ScanConfig, accumulator: _Accumulator) -> None:
    try:
        connection = _open_sqlite_snapshot(path, config.max_file_bytes)
    except _SQLiteSidecarUnsafe:
        accumulator.add(path, "sqlite.sidecar_unsafe")
        return
    except _SQLiteSizeLimit:
        accumulator.add_content_limit(path, "scan.file_size_limit")
        return
    except _SQLiteSnapshotChanged:
        accumulator.add(path, "sqlite.snapshot_changed")
        return
    except (OSError, sqlite3.Error, ValueError):
        accumulator.add(path, "sqlite.open_error")
        return

    try:
        try:
            quick = connection.execute("PRAGMA quick_check(1)").fetchall()
        except sqlite3.Error:
            accumulator.add(path, "sqlite.quick_check_error")
            return
        if quick != [("ok",)]:
            accumulator.add(path, "sqlite.quick_check_failed")

        try:
            table_names = _sqlite_table_names(connection)
        except sqlite3.Error:
            accumulator.add(path, "sqlite.schema_error")
            return

        consumed = 0
        truncated_values = 0
        row_limit_reached = False
        for table_name in table_names:
            if consumed >= config.max_sqlite_rows:
                row_limit_reached = True
                break
            try:
                cursor = connection.execute("SELECT * FROM " + _quote_identifier(table_name))
                while consumed < config.max_sqlite_rows:
                    batch = cursor.fetchmany(min(256, config.max_sqlite_rows - consumed))
                    if not batch:
                        break
                    consumed += len(batch)
                    for row in batch:
                        for value in row:
                            text, truncated = _value_text(value, config.max_sqlite_value_bytes)
                            if text is not None:
                                accumulator.add_detected(path, text)
                                if accumulator.finding_limit_reached:
                                    return
                            truncated_values += int(truncated)
                if consumed >= config.max_sqlite_rows:
                    row_limit_reached = True
                    break
            except sqlite3.Error:
                accumulator.add(path, "sqlite.table_scan_error")
        accumulator.add_content_limit(path, "scan.row_limit", int(row_limit_reached))
        accumulator.add_content_limit(path, "scan.value_limit", truncated_values)
    finally:
        connection.close()


def scan_tree(config: ScanConfig) -> ScanReport:
    """Scan a file or tree without modifying source files or persisting content."""

    normalized = config.normalized()
    accumulator = _Accumulator(normalized.root, normalized.max_findings)
    for path in _iter_paths(normalized.root, accumulator):
        if accumulator.finding_limit_reached:
            break
        if accumulator.files_seen >= normalized.max_files:
            accumulator.file_limit_reached = True
            break
        accumulator.files_seen += 1
        try:
            metadata = path.lstat()
        except OSError:
            accumulator.add(path, "scan.metadata_error")
            continue
        if _is_link_like(path, metadata):
            accumulator.add(path, "scan.symlink_skipped")
            continue
        if not stat.S_ISREG(metadata.st_mode):
            accumulator.add(path, "scan.non_regular_skipped")
            continue
        if _POSIX_MODE_SEMANTICS and metadata.st_mode & 0o077:
            accumulator.add(path, "permissions.group_or_other")
            if accumulator.finding_limit_reached:
                break

        suffix = path.suffix.lower()
        recognized_text = suffix in TEXT_SUFFIXES | JSON_SUFFIXES | JSONL_SUFFIXES
        if metadata.st_size > normalized.max_file_bytes and recognized_text:
            accumulator.add_content_limit(path, "scan.file_size_limit")
            continue

        try:
            prefix = _read_prefix(path)
        except OSError:
            accumulator.add(path, "scan.read_error")
            continue
        if _sqlite_candidate(path, prefix):
            accumulator.files_scanned += 1
            _scan_sqlite(path, normalized, accumulator)
            continue
        if not recognized_text:
            continue
        try:
            data = _read_regular_file(path, normalized.max_file_bytes)
        except OSError:
            accumulator.add(path, "scan.read_error")
            continue
        if data is None:
            accumulator.add_content_limit(path, "scan.file_size_limit")
            continue
        accumulator.files_scanned += 1
        kind = "json" if suffix in JSON_SUFFIXES else "jsonl" if suffix in JSONL_SUFFIXES else "text"
        _scan_text_file(path, data, kind, accumulator)
    return accumulator.report()
