"""Composable parameter-space primitives used by AEDT semantic sweeps.

This file owns only sweep-space semantics: axis declarations, Cartesian
expansion, and stable per-point identifiers. It does not own any AEDT
geometry, solver, HPC policy, or runtime-bundle behavior.
"""

from __future__ import annotations

import keyword
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from itertools import product
from typing import Any


def _slugify(value: Any) -> str:
    """Return a deterministic filename-safe representation for one coordinate."""

    return re.sub(r"[^0-9A-Za-z_.-]+", "-", str(value)).strip("-_") or "value"


def _ensure_unique_names(axes: tuple[Axis, ...]) -> None:
    names = [axis.name for axis in axes]
    if len(names) != len(set(names)):
        raise ValueError("axis names must be unique")


@dataclass(frozen=True)
class Axis:
    """Named 1D value axis in a sweep space.

    The axis stores a stable name, non-empty value list, and default value.

    Args:
        name: Stable axis key.
        values: Ordered sample values.
        default: Optional default value. Defaults to first entry when omitted.
    """

    name: str
    values: tuple[Any, ...]
    default: Any | None = None

    def __post_init__(self) -> None:
        if not self.name or not self.name.isidentifier() or keyword.iskeyword(self.name):
            raise ValueError(f"axis name must be a Python keyword-argument name: {self.name!r}")
        if not self.values:
            raise ValueError(f"axis {self.name!r} values cannot be empty")
        values = tuple(self.values)
        default = values[0] if self.default is None else self.default
        if default not in values:
            raise ValueError(f"axis {self.name!r} default {self.default!r} is not in values")
        object.__setattr__(self, "values", values)
        object.__setattr__(self, "default", default)


@dataclass(frozen=True)
class Point:
    """Concrete point in a ``ParameterSpace`` with stable identity."""

    id: str
    coords: Mapping[str, Any]


class ParameterSpace:
    """Finite combinatorial product space over ordered 1D axes."""

    def __init__(self, *axes: Axis):
        _ensure_unique_names(axes)
        self.axes = tuple(axes)
        self._axes_by_name = {axis.name: axis for axis in self.axes}

    @property
    def axis_names(self) -> tuple[str, ...]:
        return tuple(axis.name for axis in self.axes)

    def _validate_known_axes(self, axis_names: Iterable[str]) -> None:
        for name in axis_names:
            if name not in self._axes_by_name:
                raise ValueError(f"unknown axis: {name!r}")

    def _resolve(self, fixed: Mapping[str, Any]) -> dict[str, Any]:
        self._validate_known_axes(fixed.keys())
        resolved: dict[str, Any] = {}
        for axis in self.axes:
            value = fixed.get(axis.name, axis.default)
            if value not in axis.values:
                raise ValueError(f"axis {axis.name!r} does not include value {value!r}")
            resolved[axis.name] = value
        return resolved

    def point(self, **fixed: Any) -> Point:
        """Return one point with unspecified axes defaulted."""

        coords = self._resolve(fixed)
        return Point(id=self.point_id(**coords), coords=coords)

    def point_id(self, **coords: Any) -> str:
        """Create a stable file-safe id from coordinates in axis order."""

        self._validate_known_axes(coords.keys())
        if len(coords) != len(self.axes):
            missing = ", ".join(sorted(set(self.axis_names) - set(coords)))
            raise ValueError(f"missing axis coordinates: {missing}")
        return "__".join(f"{axis.name}={_slugify(coords[axis.name])}" for axis in self.axes)

    def grid(self) -> list[Point]:
        """Return the full Cartesian grid for all axes."""

        value_axes = [axis.values for axis in self.axes]
        points = []
        for values in product(*value_axes):
            coords = dict(zip(self.axis_names, values, strict=True))
            points.append(Point(id=self.point_id(**coords), coords=coords))
        return points

    def line(self, axis: str, **fixed: Any) -> list[Point]:
        """Vary one axis; fix all others."""

        return self.slice((axis,), **fixed)

    def plane(self, a: str, b: str, **fixed: Any) -> list[Point]:
        """Vary two axes; fix all others."""

        return self.slice((a, b), **fixed)

    def slice(self, vary: str | tuple[str, ...], **fixed: Any) -> list[Point]:
        """Vary selected axes; fix all others to defaults or explicit values."""

        vary_names = (vary,) if isinstance(vary, str) else tuple(vary)
        self._validate_known_axes(vary_names)
        if len(set(vary_names)) != len(vary_names):
            raise ValueError("vary axes must be unique")

        base = self._resolve(fixed)
        vary_axes = [self._axes_by_name[name] for name in vary_names]
        points: list[Point] = []
        for values in product(*[axis.values for axis in vary_axes]):
            coords = dict(base)
            for index, name in enumerate(vary_names):
                coords[name] = values[index]
            points.append(Point(id=self.point_id(**coords), coords=coords))
        return points


__all__ = ["Axis", "Point", "ParameterSpace"]
