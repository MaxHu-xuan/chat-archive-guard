# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import shutil
import sqlite3
import stat
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from scripts import privacy_audit
from chat_archive_guard.cli import main as cli_main
from chat_archive_guard.detectors import detect_text
from chat_archive_guard.scanner import (
    MAX_ALLOWED_FILE_BYTES,
    MAX_ALLOWED_FILES,
    MAX_ALLOWED_FINDINGS,
    MAX_ALLOWED_SQLITE_ROWS,
    MAX_ALLOWED_SQLITE_VALUE_BYTES,
    ScanConfig,
    scan_tree,
)


SECURE_SQLITE_SNAPSHOTS = isinstance(getattr(os, "O_NOFOLLOW", None), int) and bool(
    getattr(os, "O_NOFOLLOW", 0)
)


def synthetic_provider_key() -> str:
    return "".join(("s", "k", "-", "Q" * 32))


def synthetic_email() -> str:
    return "".join(("archive", chr(64), "example", ".", "invalid"))


def synthetic_sensitive_values() -> dict:
    return {
        "secret.private_key": "-----BEGIN " + "PRIVATE KEY-----",
        "secret.provider_key": synthetic_provider_key(),
        "secret.bearer_token": "Bearer " + "B" * 24,
        "secret.assignment": "pass" + "word=" + "C" * 16,
        "secret.jwt": ".".join(("eyJ" + "D" * 12, "E" * 12, "F" * 12)),
        "pii.email": synthetic_email(),
        "pii.phone_cn": "139" + "0000" + "1234",
        "pii.phone_nanp": "+1 " + "415" + " 555 " + "2671",
        "pii.national_id_cn": "110105" + "19491231" + "002X",
        "pii.ip_address": "192" + ".0.2.1",
        "pii.payment_card": "4111" + "1111" + "1111" + "1111",
    }


def categories(report) -> dict:
    values = {}
    for finding in report.findings:
        values[finding.category] = values.get(finding.category, 0) + finding.count
    return values


class TextAndFormatTests(unittest.TestCase):
    def test_counts_only_json_and_no_secret_echo(self) -> None:
        secret = synthetic_provider_key()
        contact = synthetic_email()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            archive = root / "archive.json"
            archive.write_text(
                json.dumps({"credential": secret, "contact": contact}),
                encoding="utf-8",
            )
            archive.chmod(0o600)

            report = scan_tree(ScanConfig(root=root))
            payload = json.dumps(report.to_dict(), sort_keys=True)

            self.assertGreaterEqual(categories(report).get("secret.provider_key", 0), 1)
            self.assertGreaterEqual(categories(report).get("pii.email", 0), 1)
            self.assertNotIn(secret, payload)
            self.assertNotIn(contact, payload)
            self.assertNotIn(str(root), payload)
            self.assertEqual(report.findings[0].path, "archive.json")

    def test_all_documented_sensitive_shapes_are_counts_only(self) -> None:
        values = synthetic_sensitive_values()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            archive = root / "archive.txt"
            archive.write_text("\n".join(values.values()), encoding="utf-8")
            archive.chmod(0o600)

            report = scan_tree(ScanConfig(root=root))
            rendered = json.dumps(report.to_dict(), sort_keys=True)
            observed = categories(report)

            for category, value in values.items():
                with self.subTest(category=category):
                    self.assertGreaterEqual(observed.get(category, 0), 1)
                    self.assertNotIn(value, rendered)
            self.assertNotIn(str(root), rendered)

            for arguments in ([str(root)], [str(root), "--json"]):
                stdout = io.StringIO()
                stderr = io.StringIO()
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(
                    stderr
                ):
                    result = cli_main(arguments)
                self.assertEqual(result, 1)
                self.assertEqual(stderr.getvalue(), "")
                self.assertNotIn(str(root), stdout.getvalue())
                for value in values.values():
                    self.assertNotIn(value, stdout.getvalue())
                    self.assertNotIn(value, stderr.getvalue())

    def test_regular_file_scan_does_not_modify_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            archive = root / "archive.txt"
            archive.write_text("safe", encoding="utf-8")
            archive.chmod(0o600)
            before = archive.stat()
            before_digest = hashlib.sha256(archive.read_bytes()).digest()
            before_names = {path.name for path in root.iterdir()}

            report = scan_tree(ScanConfig(root=root))

            after = archive.stat()
            self.assertTrue(report.ok)
            self.assertEqual(before_digest, hashlib.sha256(archive.read_bytes()).digest())
            self.assertEqual(before_names, {path.name for path in root.iterdir()})
            self.assertEqual(stat.S_IMODE(before.st_mode), stat.S_IMODE(after.st_mode))
            self.assertEqual(before.st_size, after.st_size)
            self.assertEqual(before.st_mtime_ns, after.st_mtime_ns)

    def test_text_size_limit_marks_report_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            archive = root / "archive.txt"
            archive.write_text("x" * 64, encoding="utf-8")
            archive.chmod(0o600)

            report = scan_tree(ScanConfig(root=root, max_file_bytes=32))

            self.assertEqual(categories(report).get("scan.file_size_limit"), 1)
            self.assertFalse(report.ok)
            self.assertFalse(report.complete)
            self.assertTrue(report.truncated)

    def test_jsonl_format_errors_are_aggregated(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            archive = root / "events.jsonl"
            archive.write_text('{"ok":true}\nnot-json\n{"also":"ok"}\n{broken\n', encoding="utf-8")
            archive.chmod(0o600)

            report = scan_tree(ScanConfig(root=root))

            self.assertEqual(categories(report).get("format.invalid_jsonl"), 2)
            finding = next(item for item in report.findings if item.category == "format.invalid_jsonl")
            self.assertEqual(finding.path, "events.jsonl")

    def test_invalid_json_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            archive = root / "broken.json"
            archive.write_text('{"unfinished":', encoding="utf-8")
            archive.chmod(0o600)

            report = scan_tree(ScanConfig(root=root))

            self.assertEqual(categories(report).get("format.invalid_json"), 1)

    def test_permissions_are_reported_without_mode_details(self) -> None:
        if os.name != "posix":
            self.skipTest("POSIX mode bits are unavailable")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            private = root / "private.txt"
            broad = root / "broad.txt"
            private.write_text("private", encoding="utf-8")
            broad.write_text("broad", encoding="utf-8")
            private.chmod(0o600)
            broad.chmod(0o640)

            report = scan_tree(ScanConfig(root=root))
            permission_findings = [item for item in report.findings if item.category == "permissions.group_or_other"]

            self.assertEqual(len(permission_findings), 1)
            self.assertEqual(permission_findings[0].path, "broad.txt")
            self.assertEqual(permission_findings[0].count, 1)

    def test_non_posix_mode_bits_are_not_misreported_as_acl_findings(self) -> None:
        from chat_archive_guard import scanner

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            archive = root / "archive.txt"
            archive.write_text("safe", encoding="utf-8")
            archive.chmod(0o640)

            with mock.patch.object(scanner, "_POSIX_MODE_SEMANTICS", False):
                report = scan_tree(ScanConfig(root=root))

            self.assertTrue(report.ok)
            self.assertNotIn("permissions.group_or_other", categories(report))

    def test_symlink_is_not_followed(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks unavailable")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            target = root / "target.txt"
            target.write_text("safe", encoding="utf-8")
            target.chmod(0o600)
            link = root / "link.txt"
            try:
                link.symlink_to(target)
            except OSError:
                self.skipTest("symlink creation is unavailable")

            report = scan_tree(ScanConfig(root=root))

            skipped = [item for item in report.findings if item.category == "scan.symlink_skipped"]
            self.assertEqual(len(skipped), 1)
            self.assertEqual(skipped[0].path, "link.txt")


class DetectorComplexityTests(unittest.TestCase):
    def test_email_detector_has_an_adversarial_runtime_gate(self) -> None:
        adversarial = ("a." * 100_000) + ("a" + chr(64)) * 100_000
        started = time.perf_counter()

        result = detect_text(adversarial)
        elapsed = time.perf_counter() - started

        self.assertNotIn("pii.email", result)
        self.assertLess(elapsed, 2.0)

    def test_bounded_email_is_still_detected(self) -> None:
        self.assertEqual(detect_text(synthetic_email()).get("pii.email"), 1)


class SQLiteTests(unittest.TestCase):
    @unittest.skipUnless(
        SECURE_SQLITE_SNAPSHOTS,
        "secure SQLite snapshots require O_NOFOLLOW",
    )
    def test_wal_visible_snapshot_is_read_only_and_value_free(self) -> None:
        secret = synthetic_provider_key()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            database = root / "events.sqlite"
            writer = sqlite3.connect(str(database))
            try:
                mode = writer.execute("PRAGMA journal_mode = WAL").fetchone()[0]
                if str(mode).lower() != "wal":
                    self.skipTest("WAL unavailable")
                writer.execute("PRAGMA wal_autocheckpoint = 0")
                writer.execute("CREATE TABLE events (body TEXT NOT NULL)")
                writer.commit()
                writer.execute("INSERT INTO events(body) VALUES (?)", (secret,))
                writer.commit()
                database.chmod(0o600)
                wal = Path(str(database) + "-wal")
                self.assertTrue(wal.exists())
                source_parts = [database, wal, Path(str(database) + "-shm")]
                self.assertTrue(source_parts[2].exists())
                for part in source_parts:
                    part.chmod(0o600)
                before_hashes = {
                    part.name: hashlib.sha256(part.read_bytes()).digest()
                    for part in source_parts
                    if part.exists()
                }
                before_names = {path.name for path in root.iterdir()}

                report = scan_tree(ScanConfig(root=root))
                payload = json.dumps(report.to_dict(), sort_keys=True)

                self.assertGreaterEqual(categories(report).get("secret.provider_key", 0), 1)
                self.assertNotIn(secret, payload)
                self.assertNotIn(str(root), payload)
                self.assertNotIn("sqlite.quick_check_failed", categories(report))
                self.assertNotIn("sqlite.quick_check_error", categories(report))
                for arguments in ([str(root)], [str(root), "--json"]):
                    stdout = io.StringIO()
                    stderr = io.StringIO()
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(
                        stderr
                    ):
                        result = cli_main(arguments)
                    self.assertEqual(result, 1)
                    self.assertEqual(stderr.getvalue(), "")
                    self.assertNotIn(secret, stdout.getvalue())
                    self.assertNotIn(str(root), stdout.getvalue())
                after_hashes = {
                    part.name: hashlib.sha256(part.read_bytes()).digest()
                    for part in source_parts
                    if part.exists()
                }
                self.assertEqual(before_hashes, after_hashes)
                self.assertEqual(before_names, {path.name for path in root.iterdir()})
            finally:
                writer.close()

    @unittest.skipUnless(
        SECURE_SQLITE_SNAPSHOTS,
        "secure SQLite snapshots require O_NOFOLLOW",
    )
    def test_wal_without_source_shm_is_visible_and_no_sidecar_is_created(self) -> None:
        secret = synthetic_provider_key()
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp).resolve()
            origin = base / "origin"
            root = base / "scan"
            origin.mkdir()
            root.mkdir()
            source_database = origin / "source.sqlite"
            writer = sqlite3.connect(str(source_database))
            try:
                mode = writer.execute("PRAGMA journal_mode = WAL").fetchone()[0]
                if str(mode).lower() != "wal":
                    self.skipTest("WAL unavailable")
                writer.execute("PRAGMA wal_autocheckpoint = 0")
                writer.execute("CREATE TABLE events (body TEXT NOT NULL)")
                writer.commit()
                writer.execute("INSERT INTO events(body) VALUES (?)", (secret,))
                writer.commit()

                database = root / "events.sqlite"
                wal = Path(str(database) + "-wal")
                shutil.copyfile(source_database, database)
                shutil.copyfile(Path(str(source_database) + "-wal"), wal)
                database.chmod(0o600)
                wal.chmod(0o600)
                before_hashes = {
                    database.name: hashlib.sha256(database.read_bytes()).digest(),
                    wal.name: hashlib.sha256(wal.read_bytes()).digest(),
                }
                before_names = {path.name for path in root.iterdir()}

                report = scan_tree(ScanConfig(root=root))

                self.assertEqual(categories(report).get("secret.provider_key"), 1)
                self.assertEqual(before_names, {path.name for path in root.iterdir()})
                self.assertFalse(Path(str(database) + "-shm").exists())
                self.assertEqual(
                    before_hashes,
                    {
                        database.name: hashlib.sha256(database.read_bytes()).digest(),
                        wal.name: hashlib.sha256(wal.read_bytes()).digest(),
                    },
                )
            finally:
                writer.close()

    @unittest.skipUnless(
        SECURE_SQLITE_SNAPSHOTS,
        "secure SQLite snapshots require O_NOFOLLOW",
    )
    def test_sqlite_is_only_opened_from_private_modes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            database = root / "events.sqlite"
            writer = sqlite3.connect(str(database))
            try:
                mode = writer.execute("PRAGMA journal_mode = WAL").fetchone()[0]
                if str(mode).lower() != "wal":
                    self.skipTest("WAL unavailable")
                writer.execute("PRAGMA wal_autocheckpoint = 0")
                writer.execute("CREATE TABLE events (body TEXT NOT NULL)")
                writer.execute("INSERT INTO events(body) VALUES ('safe')")
                writer.commit()
                source_names = {"events.sqlite", "events.sqlite-wal", "events.sqlite-shm"}
                for source_name in source_names:
                    (root / source_name).chmod(0o600)
                real_connect = sqlite3.connect
                observed_private = []

                def checked_connect(target, *args, **kwargs):
                    self.assertNotEqual(str(target), str(database))
                    self.assertNotEqual(str(target), database.as_uri() + "?mode=ro")
                    if kwargs.get("uri"):
                        private_path = Path(str(target).split("?", 1)[0][len("file://"):])
                        self.assertNotEqual(private_path, database)
                        self.assertEqual(stat.S_IMODE(private_path.parent.stat().st_mode), 0o700)
                        private_parts = {part.name for part in private_path.parent.iterdir()}
                        self.assertEqual(
                            private_parts,
                            {"database.sqlite", "database.sqlite-wal", "database.sqlite-shm"},
                        )
                        for part in private_path.parent.iterdir():
                            self.assertEqual(stat.S_IMODE(part.stat().st_mode), 0o600)
                        observed_private.append(private_path)
                    return real_connect(target, *args, **kwargs)

                with mock.patch("chat_archive_guard.scanner.sqlite3.connect", side_effect=checked_connect):
                    report = scan_tree(ScanConfig(root=root))

                self.assertTrue(report.ok)
                self.assertEqual(len(observed_private), 1)
                self.assertFalse(observed_private[0].parent.exists())
            finally:
                writer.close()

    def test_sidecar_symlinks_fail_closed(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks unavailable")
        for suffix in ("-wal", "-shm"):
            with self.subTest(suffix=suffix), tempfile.TemporaryDirectory() as temp:
                root = Path(temp).resolve()
                database = root / "events.sqlite"
                with sqlite3.connect(str(database)) as connection:
                    connection.execute("CREATE TABLE events (body TEXT NOT NULL)")
                database.chmod(0o600)
                external = root.parent / (root.name + "-external")
                external.write_text(synthetic_provider_key(), encoding="utf-8")
                external.chmod(0o600)
                sidecar = Path(str(database) + suffix)
                try:
                    sidecar.symlink_to(external)
                except OSError:
                    self.skipTest("symlink creation is unavailable")
                try:
                    report = scan_tree(ScanConfig(root=root))
                    payload = json.dumps(report.to_dict(), sort_keys=True)
                    self.assertEqual(categories(report).get("sqlite.sidecar_unsafe"), 1)
                    self.assertNotIn(synthetic_provider_key(), payload)
                finally:
                    external.unlink()

    @unittest.skipUnless(
        SECURE_SQLITE_SNAPSHOTS,
        "secure SQLite snapshots require O_NOFOLLOW",
    )
    def test_snapshot_identity_change_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            database = root / "events.sqlite"
            with sqlite3.connect(str(database)) as connection:
                connection.execute("CREATE TABLE events (body TEXT NOT NULL)")
            database.chmod(0o600)
            from chat_archive_guard import scanner

            original_copy = scanner._copy_sqlite_part

            def changing_copy(source, destination, expected):
                digest = original_copy(source, destination, expected)
                os.utime(
                    source,
                    ns=(expected.modified_ns, expected.modified_ns + 1_000_000_000),
                )
                return digest

            with mock.patch("chat_archive_guard.scanner._copy_sqlite_part", side_effect=changing_copy):
                report = scan_tree(ScanConfig(root=root))

            self.assertEqual(categories(report).get("sqlite.snapshot_changed"), 1)

    @unittest.skipUnless(
        SECURE_SQLITE_SNAPSHOTS,
        "secure SQLite snapshots require O_NOFOLLOW",
    )
    def test_snapshot_hash_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            database = root / "events.sqlite"
            with sqlite3.connect(str(database)) as connection:
                connection.execute("CREATE TABLE events (body TEXT NOT NULL)")
            database.chmod(0o600)

            with mock.patch(
                "chat_archive_guard.scanner._hash_sqlite_part",
                return_value=b"\x00" * 32,
            ):
                report = scan_tree(ScanConfig(root=root))

            self.assertEqual(categories(report).get("sqlite.snapshot_changed"), 1)

    @unittest.skipUnless(
        SECURE_SQLITE_SNAPSHOTS,
        "secure SQLite snapshots require O_NOFOLLOW",
    )
    def test_sidecar_appearing_during_snapshot_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            database = root / "events.sqlite"
            with sqlite3.connect(str(database)) as connection:
                connection.execute("CREATE TABLE events (body TEXT NOT NULL)")
            database.chmod(0o600)
            from chat_archive_guard import scanner

            original_copy = scanner._copy_sqlite_part
            appeared = False

            def copy_then_add_sidecar(source, destination, expected):
                nonlocal appeared
                digest = original_copy(source, destination, expected)
                if not appeared:
                    sidecar = Path(str(database) + "-wal")
                    sidecar.write_bytes(b"synthetic concurrent sidecar")
                    sidecar.chmod(0o600)
                    appeared = True
                return digest

            with mock.patch(
                "chat_archive_guard.scanner._copy_sqlite_part",
                side_effect=copy_then_add_sidecar,
            ):
                report = scan_tree(ScanConfig(root=root))

            self.assertEqual(categories(report).get("sqlite.snapshot_changed"), 1)

    @unittest.skipUnless(
        SECURE_SQLITE_SNAPSHOTS,
        "secure SQLite snapshots require O_NOFOLLOW",
    )
    def test_snapshot_growth_reads_at_most_one_probe_byte(self) -> None:
        from chat_archive_guard import scanner

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            source = root / "source.sqlite"
            destination = root / "private.sqlite"
            source.write_bytes(b"x" * 4096)
            source.chmod(0o600)
            expected = scanner._FileIdentity.from_stat(source.stat())
            real_read = os.read
            returned = 0
            grew = False

            def growing_read(descriptor, length):
                nonlocal returned, grew
                chunk = real_read(descriptor, length)
                returned += len(chunk)
                if chunk and not grew:
                    with source.open("ab") as handle:
                        handle.write(b"y" * 8192)
                    grew = True
                return chunk

            with mock.patch("chat_archive_guard.scanner.os.read", side_effect=growing_read):
                with self.assertRaises(scanner._SQLiteSnapshotChanged):
                    scanner._copy_sqlite_part(source, destination, expected)

            self.assertLessEqual(returned, expected.size + 1)

    @unittest.skipUnless(
        SECURE_SQLITE_SNAPSHOTS,
        "secure SQLite snapshots require O_NOFOLLOW",
    )
    def test_corrupt_database_error_is_sanitized(self) -> None:
        marker = synthetic_provider_key()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            database = root / "broken.sqlite"
            database.write_bytes(b"SQLite format 3\x00" + marker.encode("ascii"))
            database.chmod(0o600)

            report = scan_tree(ScanConfig(root=root))
            payload = json.dumps(report.to_dict(), sort_keys=True)

            self.assertIn("sqlite.open_error", categories(report))
            self.assertNotIn(marker, payload)
            self.assertNotIn(str(root), payload)
            for arguments in ([str(root)], [str(root), "--json"]):
                stdout = io.StringIO()
                stderr = io.StringIO()
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(
                    stderr
                ):
                    result = cli_main(arguments)
                self.assertEqual(result, 1)
                self.assertEqual(stderr.getvalue(), "")
                self.assertNotIn(marker, stdout.getvalue())
                self.assertNotIn(str(root), stdout.getvalue())

    def test_sqlite_and_wal_are_bounded_before_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            database = root / "large.sqlite"
            with sqlite3.connect(str(database)) as connection:
                connection.execute("CREATE TABLE events (body BLOB NOT NULL)")
                connection.execute("INSERT INTO events(body) VALUES (?)", (b"x" * 8192,))
            database.chmod(0o600)

            report = scan_tree(ScanConfig(root=root, max_file_bytes=1024))

            self.assertEqual(categories(report).get("scan.file_size_limit"), 1)
            self.assertFalse(report.complete)
            self.assertTrue(report.truncated)

    def test_missing_o_nofollow_fails_closed_without_opening_or_mutating(self) -> None:
        from chat_archive_guard import scanner

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            database = root / "events.sqlite"
            with sqlite3.connect(str(database)) as connection:
                connection.execute("CREATE TABLE events (body TEXT NOT NULL)")
                connection.execute("INSERT INTO events(body) VALUES ('safe')")
            database.chmod(0o600)
            before_names = {path.name for path in root.iterdir()}
            before_digest = hashlib.sha256(database.read_bytes()).digest()

            with (
                mock.patch.object(scanner.os, "O_NOFOLLOW", None, create=True),
                mock.patch.object(
                    scanner.sqlite3,
                    "connect",
                    side_effect=AssertionError("source SQLite must not be opened"),
                ),
            ):
                report = scan_tree(ScanConfig(root=root))

            self.assertEqual(categories(report).get("sqlite.sidecar_unsafe"), 1)
            self.assertEqual(before_names, {path.name for path in root.iterdir()})
            self.assertEqual(before_digest, hashlib.sha256(database.read_bytes()).digest())

    @unittest.skipUnless(
        SECURE_SQLITE_SNAPSHOTS,
        "secure SQLite snapshots require O_NOFOLLOW",
    )
    def test_row_limit_is_a_finding_in_the_only_table(self) -> None:
        secret = synthetic_provider_key()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            database = root / "events.sqlite"
            with sqlite3.connect(str(database)) as connection:
                connection.execute("CREATE TABLE events (body TEXT NOT NULL)")
                connection.executemany("INSERT INTO events(body) VALUES (?)", (("safe",), (secret,)))
            database.chmod(0o600)

            report = scan_tree(ScanConfig(root=root, max_sqlite_rows=1))

            self.assertEqual(categories(report).get("scan.row_limit"), 1)
            self.assertNotIn("secret.provider_key", categories(report))
            self.assertFalse(report.ok)
            self.assertFalse(report.complete)
            self.assertTrue(report.truncated)

    @unittest.skipUnless(
        SECURE_SQLITE_SNAPSHOTS,
        "secure SQLite snapshots require O_NOFOLLOW",
    )
    def test_exact_row_limit_is_conservatively_a_finding(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            database = root / "events.sqlite"
            with sqlite3.connect(str(database)) as connection:
                connection.execute("CREATE TABLE events (body TEXT NOT NULL)")
                connection.execute("INSERT INTO events(body) VALUES ('safe')")
            database.chmod(0o600)

            report = scan_tree(ScanConfig(root=root, max_sqlite_rows=1))

            self.assertEqual(categories(report).get("scan.row_limit"), 1)
            self.assertFalse(report.ok)
            self.assertFalse(report.complete)
            self.assertTrue(report.truncated)

    @unittest.skipUnless(
        SECURE_SQLITE_SNAPSHOTS,
        "secure SQLite snapshots require O_NOFOLLOW",
    )
    def test_sqlite_value_limit_marks_report_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            database = root / "events.sqlite"
            with sqlite3.connect(str(database)) as connection:
                connection.execute("CREATE TABLE events (body TEXT NOT NULL)")
                connection.execute("INSERT INTO events(body) VALUES (?)", ("x" * 64,))
            database.chmod(0o600)

            report = scan_tree(
                ScanConfig(root=root, max_sqlite_value_bytes=16)
            )

            self.assertEqual(categories(report).get("scan.value_limit"), 1)
            self.assertFalse(report.ok)
            self.assertFalse(report.complete)
            self.assertTrue(report.truncated)

    @unittest.skipUnless(
        SECURE_SQLITE_SNAPSHOTS,
        "secure SQLite snapshots require O_NOFOLLOW",
    )
    def test_fts_shadow_content_is_counted_once(self) -> None:
        secret = synthetic_provider_key()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            database = root / "search.sqlite"
            connection = sqlite3.connect(str(database))
            try:
                try:
                    connection.execute("CREATE VIRTUAL TABLE documents USING fts5(body)")
                except sqlite3.OperationalError:
                    self.skipTest("FTS5 unavailable")
                connection.execute("INSERT INTO documents(body) VALUES (?)", (secret,))
                connection.commit()
            finally:
                connection.close()
            database.chmod(0o600)

            report = scan_tree(ScanConfig(root=root))

            self.assertEqual(categories(report).get("secret.provider_key"), 1)

    def test_fts_shadow_fallback_excludes_internal_tables(self) -> None:
        from chat_archive_guard import scanner

        with sqlite3.connect(":memory:") as connection:
            try:
                connection.execute('CREATE VIRTUAL TABLE documents USING "fts5"(body)')
            except sqlite3.OperationalError:
                self.skipTest("FTS5 unavailable")

            class LegacyTableListConnection:
                def execute(self, sql):
                    if sql == "PRAGMA table_list":
                        raise sqlite3.OperationalError("unsupported")
                    return connection.execute(sql)

            names = scanner._sqlite_table_names(LegacyTableListConnection())

        self.assertIn("documents", names)
        self.assertFalse(any(name.startswith("documents_") for name in names))


class RootBoundaryTests(unittest.TestCase):
    def test_windows_reparse_attributes_are_link_like(self) -> None:
        from chat_archive_guard import scanner

        metadata = mock.Mock(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
        with mock.patch.object(
            scanner.stat,
            "FILE_ATTRIBUTE_REPARSE_POINT",
            0x400,
            create=True,
        ):
            self.assertTrue(scanner._is_link_like(Path("synthetic"), metadata))

    def test_top_level_symlink_is_rejected(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks unavailable")
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp).resolve()
            target = base / "target"
            target.mkdir()
            link = base / "link"
            try:
                link.symlink_to(target, target_is_directory=True)
            except OSError:
                self.skipTest("symlink creation is unavailable")

            with self.assertRaises(ValueError):
                scan_tree(ScanConfig(root=link))

    def test_ancestor_symlink_is_rejected(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks unavailable")
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp).resolve()
            target = base / "target"
            child = target / "child"
            child.mkdir(parents=True)
            alias = base / "alias"
            try:
                alias.symlink_to(target, target_is_directory=True)
            except OSError:
                self.skipTest("symlink creation is unavailable")

            with self.assertRaises(ValueError):
                scan_tree(ScanConfig(root=alias / "child"))

    def test_parent_traversal_is_rejected_before_normalization(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp).resolve()
            child = base / "child"
            child.mkdir()

            with self.assertRaises(ValueError):
                scan_tree(ScanConfig(root=child / ".." / "child"))


class AggregateLimitTests(unittest.TestCase):
    def test_fifteen_hundred_files_stop_at_explicit_file_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            for index in range(1_500):
                path = root / ("item-%04d.txt" % index)
                path.write_text("", encoding="utf-8")
                path.chmod(0o600)

            report = scan_tree(
                ScanConfig(root=root, max_files=1_000, max_findings=2_000)
            )
            payload = report.to_dict()

            self.assertEqual(report.files_seen, 1_000)
            self.assertEqual(report.files_scanned, 1_000)
            self.assertEqual(categories(report).get("scan.file_limit"), 1)
            self.assertFalse(report.ok)
            self.assertFalse(report.complete)
            self.assertTrue(report.truncated)
            self.assertFalse(payload["complete"])
            self.assertTrue(payload["truncated"])

    def test_finding_limit_caps_counts_and_marks_report_incomplete(self) -> None:
        secret = synthetic_provider_key()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            path = root / "archive.txt"
            path.write_text((secret + "\n") * 20, encoding="utf-8")
            path.chmod(0o600)

            report = scan_tree(
                ScanConfig(root=root, max_files=10, max_findings=5)
            )
            rendered = json.dumps(report.to_dict(), sort_keys=True)

            self.assertEqual(categories(report).get("secret.provider_key"), 5)
            self.assertEqual(categories(report).get("scan.finding_limit"), 1)
            self.assertEqual(report.finding_count, 6)
            self.assertFalse(report.ok)
            self.assertFalse(report.complete)
            self.assertTrue(report.truncated)
            self.assertNotIn(secret, rendered)

    def test_cli_rejects_limits_above_finite_supported_maximum(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            for option, value in (
                ("--max-file-mib", MAX_ALLOWED_FILE_BYTES // (1024 * 1024) + 1),
                ("--max-sqlite-rows", MAX_ALLOWED_SQLITE_ROWS + 1),
                (
                    "--max-sqlite-value-kib",
                    MAX_ALLOWED_SQLITE_VALUE_BYTES // 1024 + 1,
                ),
                ("--max-files", MAX_ALLOWED_FILES + 1),
                ("--max-findings", MAX_ALLOWED_FINDINGS + 1),
            ):
                with self.subTest(option=option):
                    stdout = io.StringIO()
                    stderr = io.StringIO()
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(
                        stderr
                    ):
                        result = cli_main([str(root), "--json", option, str(value)])
                    payload = json.loads(stdout.getvalue())
                    self.assertEqual(result, 2)
                    self.assertFalse(payload["ok"])
                    self.assertFalse(payload["complete"])
                    self.assertFalse(payload["truncated"])
                    self.assertEqual(stderr.getvalue(), "")


class CliPrivacyTests(unittest.TestCase):
    def test_stdout_stderr_and_json_never_echo_match(self) -> None:
        secret = synthetic_provider_key()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            archive = root / "chat.txt"
            archive.write_text("credential=" + secret, encoding="utf-8")
            archive.chmod(0o600)
            stdout = io.StringIO()
            stderr = io.StringIO()

            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                result = cli_main([str(root), "--json"])

            output = stdout.getvalue()
            parsed = json.loads(output)
            self.assertEqual(result, 1)
            self.assertEqual(stderr.getvalue(), "")
            self.assertNotIn(secret, output)
            self.assertNotIn(str(root), output)
            self.assertEqual(parsed["findings"][0]["path"], "chat.txt")
            self.assertNotIn("value", parsed["findings"][0])

            human_out = io.StringIO()
            human_err = io.StringIO()
            with contextlib.redirect_stdout(human_out), contextlib.redirect_stderr(human_err):
                human_result = cli_main([str(root)])
            self.assertEqual(human_result, 1)
            self.assertEqual(human_err.getvalue(), "")
            self.assertNotIn(secret, human_out.getvalue())
            self.assertNotIn(str(root), human_out.getvalue())

    def test_cli_output_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            for name in ("z-last.txt", "a-first.txt"):
                path = root / name
                path.write_text("safe", encoding="utf-8")
                path.chmod(0o640)

            def render(arguments):
                stdout = io.StringIO()
                stderr = io.StringIO()
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(
                    stderr
                ):
                    result = cli_main(arguments)
                return result, stdout.getvalue(), stderr.getvalue()

            first_json = render([str(root), "--json"])
            second_json = render([str(root), "--json"])
            first_human = render([str(root)])
            second_human = render([str(root)])

            self.assertEqual(first_json, second_json)
            self.assertEqual(first_human, second_human)
            self.assertEqual(first_json[0], 1)
            self.assertEqual(first_human[0], 1)
            self.assertEqual(first_json[2], "")
            self.assertEqual(first_human[2], "")
            self.assertLess(first_json[1].find("a-first.txt"), first_json[1].find("z-last.txt"))
            self.assertLess(first_human[1].find("a-first.txt"), first_human[1].find("z-last.txt"))

    def test_internal_io_error_message_and_absolute_path_are_not_emitted(self) -> None:
        marker = synthetic_provider_key()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            archive = root / "archive.txt"
            archive.write_text("safe", encoding="utf-8")
            archive.chmod(0o600)

            for as_json in (False, True):
                with self.subTest(as_json=as_json):
                    stdout = io.StringIO()
                    stderr = io.StringIO()
                    arguments = [str(root)] + (["--json"] if as_json else [])
                    with mock.patch(
                        "chat_archive_guard.scanner._read_prefix",
                        side_effect=OSError(marker),
                    ):
                        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(
                            stderr
                        ):
                            result = cli_main(arguments)
                    self.assertEqual(result, 1)
                    self.assertNotIn(marker, stdout.getvalue())
                    self.assertNotIn(str(root), stdout.getvalue())
                    self.assertEqual(stderr.getvalue(), "")

    def test_fatal_error_does_not_echo_requested_path(self) -> None:
        hidden_component = synthetic_provider_key()
        missing = Path(tempfile.gettempdir()) / hidden_component / "missing"
        stdout = io.StringIO()
        stderr = io.StringIO()

        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = cli_main([str(missing), "--json"])

        self.assertEqual(result, 2)
        self.assertNotIn(hidden_component, stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")

    def test_usage_error_does_not_echo_unknown_value(self) -> None:
        hidden_component = synthetic_provider_key()
        stdout = io.StringIO()
        stderr = io.StringIO()

        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = cli_main(["--json", "--unknown", hidden_component])

        self.assertEqual(result, 2)
        self.assertNotIn(hidden_component, stdout.getvalue())
        self.assertNotIn(hidden_component, stderr.getvalue())
        self.assertEqual(stderr.getvalue(), "")

    def test_runtime_and_unicode_errors_are_fixed_and_value_free(self) -> None:
        marker = synthetic_provider_key()
        for error in (RuntimeError(marker), UnicodeError(marker)):
            with self.subTest(error=type(error).__name__):
                stdout = io.StringIO()
                stderr = io.StringIO()
                with mock.patch("chat_archive_guard.cli.scan_tree", side_effect=error):
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        result = cli_main([".", "--json"])
                self.assertEqual(result, 2)
                self.assertNotIn(marker, stdout.getvalue())
                self.assertNotIn(marker, stderr.getvalue())
                self.assertEqual(stderr.getvalue(), "")


class PrivacyAuditTests(unittest.TestCase):
    def test_bundled_self_test_passes(self) -> None:
        self.assertTrue(privacy_audit.self_test())

    def test_privacy_audit_rejects_windows_reparse_attributes(self) -> None:
        metadata = mock.Mock(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
        with mock.patch.object(
            privacy_audit.stat,
            "FILE_ATTRIBUTE_REPARSE_POINT",
            0x400,
            create=True,
        ):
            self.assertTrue(
                privacy_audit._is_link_like(Path("synthetic"), metadata)
            )

    def test_invalid_root_and_arguments_do_not_echo_values(self) -> None:
        marker = synthetic_provider_key()
        missing = Path(tempfile.gettempdir()) / marker / "missing"
        for arguments in ([str(missing)], ["--unknown", marker]):
            with self.subTest(arguments=arguments[:1]):
                stdout = io.StringIO()
                stderr = io.StringIO()
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(
                    stderr
                ):
                    result = privacy_audit.main(arguments)
                self.assertEqual(result, 1)
                self.assertNotIn(marker, stdout.getvalue())
                self.assertNotIn(marker, stderr.getvalue())
                self.assertEqual(stderr.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
