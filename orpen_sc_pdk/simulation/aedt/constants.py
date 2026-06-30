"""Shared AEDT scalar constants for host-side package validation.

This module owns small unit conversion tables used by AEDT package models and
host-side writers. Runtime scripts copied into handoff packages keep their own
self-contained constants until the runtime bundle is copied as a package.
"""

from __future__ import annotations

AEDT_MODELER_UNIT_TO_UM = {
    "nm": 0.001,
    "um": 1.0,
    "mm": 1000.0,
    "cm": 10000.0,
    "m": 1000000.0,
    "mil": 25.4,
    "in": 25400.0,
}
AEDT_MODELER_UNIT_ALIASES = {
    "micron": "um",
    "microns": "um",
    "meter": "m",
    "meters": "m",
}

__all__ = [
    "AEDT_MODELER_UNIT_ALIASES",
    "AEDT_MODELER_UNIT_TO_UM",
]
