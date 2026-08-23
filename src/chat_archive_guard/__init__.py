# SPDX-License-Identifier: Apache-2.0
"""Privacy-preserving diagnostics for local chat archives."""

from .model import Finding, ScanReport
from .scanner import ScanConfig, scan_tree

__all__ = ["Finding", "ScanConfig", "ScanReport", "scan_tree"]
__version__ = "0.1.0"
