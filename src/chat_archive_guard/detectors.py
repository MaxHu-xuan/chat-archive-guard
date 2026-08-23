# SPDX-License-Identifier: Apache-2.0
"""Content detectors that return category counts, never matching values."""

from __future__ import annotations

import ipaddress
import re
from collections import Counter
from typing import Counter as CounterType


_REGEXES = {
    "secret.private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "secret.provider_key": re.compile(
        r"(?<![A-Za-z0-9])(?:sk-[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{12,}|gh[pousr]_[A-Za-z0-9]{20,})(?![A-Za-z0-9])"
    ),
    "secret.bearer_token": re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{12,}"),
    "secret.assignment": re.compile(
        r"(?i)\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|password|passwd)\b"
        r"\s*[:=]\s*[\"']?[A-Za-z0-9._~+/=-]{8,}"
    ),
    "secret.jwt": re.compile(r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}(?![A-Za-z0-9_-])"),
    # Bounded components and a left boundary make failed searches linear in the
    # input size instead of repeatedly rescanning an unbounded local part.
    "pii.email": re.compile(
        r"(?<![A-Z0-9._%+-])[A-Z0-9._%+-]{1,64}@[A-Z0-9.-]{1,253}"
        r"\.[A-Z]{2,63}(?![A-Z0-9.-])",
        re.IGNORECASE | re.ASCII,
    ),
    "pii.phone_cn": re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)"),
    "pii.phone_nanp": re.compile(r"(?<!\d)(?:\+?1[- .]?)?(?:\(?[2-9]\d{2}\)?[- .]?)\d{3}[- .]?\d{4}(?!\d)"),
    "pii.national_id_cn": re.compile(r"(?<!\d)\d{17}[0-9Xx](?!\d)"),
}

_IPV4_CANDIDATE = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
_CARD_CANDIDATE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")


def _luhn_ok(digits: str) -> bool:
    if not 13 <= len(digits) <= 19 or len(set(digits)) == 1:
        return False
    total = 0
    parity = len(digits) % 2
    for index, char in enumerate(digits):
        value = ord(char) - ord("0")
        if index % 2 == parity:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def detect_text(text: str) -> CounterType[str]:
    """Return counts by category without retaining any matching text."""

    counts: CounterType[str] = Counter()
    for category, pattern in _REGEXES.items():
        count = sum(1 for _ in pattern.finditer(text))
        if count:
            counts[category] += count

    valid_ips = 0
    for match in _IPV4_CANDIDATE.finditer(text):
        try:
            address = ipaddress.ip_address(match.group(0))
        except ValueError:
            continue
        if isinstance(address, ipaddress.IPv4Address):
            valid_ips += 1
    if valid_ips:
        counts["pii.ip_address"] += valid_ips

    cards = 0
    for match in _CARD_CANDIDATE.finditer(text):
        digits = re.sub(r"\D", "", match.group(0))
        if _luhn_ok(digits):
            cards += 1
    if cards:
        counts["pii.payment_card"] += cards
    return counts
