# SPDX-License-Identifier: Apache-2.0
"""Deliberately small, value-free report model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Tuple


@dataclass(frozen=True, order=True)
class Finding:
    """An aggregate finding that never contains matched content."""

    path: str
    category: str
    count: int

    def to_dict(self) -> Dict[str, object]:
        return {"path": self.path, "category": self.category, "count": self.count}


@dataclass(frozen=True)
class ScanReport:
    """Serializable scan result with relative paths and aggregate counts only."""

    files_seen: int
    files_scanned: int
    findings: Tuple[Finding, ...]
    complete: bool = True
    truncated: bool = False

    @property
    def finding_count(self) -> int:
        return sum(item.count for item in self.findings)

    @property
    def ok(self) -> bool:
        return self.complete and not self.truncated and not self.findings

    def category_counts(self) -> Dict[str, int]:
        """Return deterministic aggregate counts without paths or values."""

        categories: Dict[str, int] = {}
        for item in self.findings:
            categories[item.category] = categories.get(item.category, 0) + item.count
        return dict(sorted(categories.items()))

    def _summary(self) -> Dict[str, object]:
        return {
            "files_seen": self.files_seen,
            "files_scanned": self.files_scanned,
            "finding_count": self.finding_count,
            "categories": self.category_counts(),
        }

    def to_dict(self) -> Dict[str, object]:
        """Return the stable default report, including relative finding paths."""

        return {
            "schema_version": 1,
            "ok": self.ok,
            "complete": self.complete,
            "truncated": self.truncated,
            "root": ".",
            "summary": self._summary(),
            "findings": [item.to_dict() for item in self.findings],
        }

    def to_summary_dict(self) -> Dict[str, object]:
        """Return an aggregate-only report with all finding rows omitted."""

        return {
            "schema_version": 1,
            "report_mode": "summary-only",
            "ok": self.ok,
            "complete": self.complete,
            "truncated": self.truncated,
            "root": ".",
            "summary": self._summary(),
            "details_omitted": True,
            "findings_omitted": True,
        }


def build_findings(counts: Mapping[Tuple[str, str], int]) -> Tuple[Finding, ...]:
    items: List[Finding] = []
    for (path, category), count in counts.items():
        if count > 0:
            items.append(Finding(path=path, category=category, count=int(count)))
    return tuple(sorted(items))
