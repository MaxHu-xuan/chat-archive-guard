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

    def to_dict(self) -> Dict[str, object]:
        categories: Dict[str, int] = {}
        for item in self.findings:
            categories[item.category] = categories.get(item.category, 0) + item.count
        return {
            "schema_version": 1,
            "ok": self.ok,
            "complete": self.complete,
            "truncated": self.truncated,
            "root": ".",
            "summary": {
                "files_seen": self.files_seen,
                "files_scanned": self.files_scanned,
                "finding_count": self.finding_count,
                "categories": dict(sorted(categories.items())),
            },
            "findings": [item.to_dict() for item in self.findings],
        }


def build_findings(counts: Mapping[Tuple[str, str], int]) -> Tuple[Finding, ...]:
    items: List[Finding] = []
    for (path, category), count in counts.items():
        if count > 0:
            items.append(Finding(path=path, category=category, count=int(count)))
    return tuple(sorted(items))
