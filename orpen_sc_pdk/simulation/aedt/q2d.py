"""Semantic Q2D cross-section contract for AEDT handoff packages.

This module owns the notebook-side vocabulary for Q2D geometry after removing
the CPW/GDS-derived native rectangle path. A Q2D cross-section is now described
by an explicit vertical stack plus explicit metal sequences on named die faces.
It does not infer conductors from GDSFactory layout, CPW marker ports, or layer
mapping sidecars.

The runtime compiler that turns this contract into AEDT rectangles lives in the
copied AEDT handoff runtime bundle, so generated packages stay executable on a
target AEDT machine without importing this checkout.
"""

from __future__ import annotations

import csv
import importlib
import json
import math
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from .parameter_space import ParameterSpace

FaceName = Literal["top", "bottom"]
GapRole = Literal["lateral_spacing", "upper_ground_clearance"]
Q2dMatrixSource = Literal["cg_maxwell", "rl_maxwell", "cg_couple", "rl_couple"]
Q2dMatrixQuantity = Literal["C", "G", "L", "R"]

_Q2D_RAW_MATRIX_FILES: dict[Q2dMatrixSource, str] = {
    "cg_maxwell": "cg_maxwell_matrix.csv",
    "rl_maxwell": "rl_maxwell_matrix.csv",
    "cg_couple": "cg_couple_matrix.csv",
    "rl_couple": "rl_couple_matrix.csv",
}


def _sorted_fieldnames(rows: Sequence[dict[str, Any]]) -> list[str]:
    return list(dict.fromkeys(key for row in rows for key in row))


def _file_slug(value: Any) -> str:
    return re.sub(r"[^0-9A-Za-z_.-]+", "-", str(value)).strip("-_") or "value"


def _sorted_unique(values: Iterable[Any]) -> tuple[Any, ...]:
    unique = list(dict.fromkeys(value for value in values if value is not None))
    try:
        return tuple(sorted(unique))
    except TypeError:
        return tuple(sorted(unique, key=str))


def _numeric_values(values: Sequence[Any], field: str) -> tuple[float, ...]:
    try:
        return tuple(float(value) for value in values)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Q2dFacetLineGrid color field must be numeric: {field}") from exc


def _normalized(value: float, minimum: float, maximum: float) -> float:
    return 0.5 if maximum == minimum else (value - minimum) / (maximum - minimum)


def _format_value(value: Any) -> str:
    return f"{value:g}" if isinstance(value, int | float) else str(value)


def _matches_filter(value: Any, condition: Any) -> bool:
    if callable(condition):
        return bool(condition(value))
    if isinstance(condition, tuple | list | set | frozenset):
        return value in condition
    return value == condition


@dataclass(frozen=True, slots=True)
class Air:
    """Exterior simulation margin used to size the single AEDT Vacuum region.

    ``Air`` is not emitted as a dielectric object. It may appear only at the
    bottom and/or top of the stack.
    """

    height_um: float

    def __post_init__(self) -> None:
        _require_positive("Air.height_um", self.height_um)


@dataclass(frozen=True, slots=True)
class DieGap:
    """Physical empty spacing between die substrates.

    ``DieGap`` reserves vertical space in the stack. It is not emitted as a
    rectangle; the final Vacuum region owns the empty volume.
    """

    height_um: float

    def __post_init__(self) -> None:
        _require_positive("DieGap.height_um", self.height_um)


@dataclass(frozen=True, slots=True)
class Die:
    """Substrate body that will become one Q2D dielectric rectangle."""

    id: str
    thickness_um: float
    material: str = "Silicon"

    def __post_init__(self) -> None:
        _require_name("Die.id", self.id)
        _require_positive("Die.thickness_um", self.thickness_um)
        _require_name("Die.material", self.material)


StackElement = Air | Die | DieGap


@dataclass(frozen=True, slots=True)
class Stack:
    """Bottom-to-top Q2D vertical stack.

    The sequence is the source of truth for die placement. Exterior ``Air``
    elements size the Vacuum region; ``DieGap`` elements model internal empty
    spacing; only ``Die`` elements become material rectangles.
    """

    elements: tuple[StackElement, ...]

    def __post_init__(self) -> None:
        if not self.elements:
            raise ValueError("Stack.elements must not be empty")
        die_ids = [element.id for element in self.elements if isinstance(element, Die)]
        if not die_ids:
            raise ValueError("Stack requires at least one Die")
        duplicates = sorted({die_id for die_id in die_ids if die_ids.count(die_id) > 1})
        if duplicates:
            raise ValueError(f"Stack Die ids must be unique: {duplicates}")
        for index, element in enumerate(self.elements[1:-1], start=1):
            if isinstance(element, Air):
                raise ValueError(f"Air is only allowed at stack edges; got Air at index {index}")


@dataclass(frozen=True, slots=True)
class Ground:
    """Reference-ground metal segment on one die face."""

    width_um: float

    def __post_init__(self) -> None:
        _require_positive("Ground.width_um", self.width_um)


@dataclass(frozen=True, slots=True)
class Gap:
    """Empty lateral spacing between face metal segments.

    ``upper_ground_clearance`` identifies a local opening in an otherwise
    present upper ground plane. The role changes semantic provenance only;
    every gap still advances the Q2D lateral cursor without emitting metal.
    """

    width_um: float
    role: GapRole = "lateral_spacing"

    def __post_init__(self) -> None:
        _require_positive("Gap.width_um", self.width_um)
        if self.role not in {"lateral_spacing", "upper_ground_clearance"}:
            raise ValueError(f"Unsupported Gap.role: {self.role!r}")


@dataclass(frozen=True, slots=True)
class Trace:
    """Signal metal segment on one die face."""

    name: str
    width_um: float

    def __post_init__(self) -> None:
        _require_name("Trace.name", self.name)
        _require_positive("Trace.width_um", self.width_um)


FaceSegment = Ground | Gap | Trace


@dataclass(frozen=True, slots=True)
class FacePattern:
    """Explicit left-to-right metal sequence on one named die face."""

    die: str
    face: FaceName
    metal_thickness_um: float
    segments: tuple[FaceSegment, ...]
    x0_um: float = 0.0
    ground_assignment_name: str = "Ground"
    material: str = "pec"

    def __post_init__(self) -> None:
        _require_name("FacePattern.die", self.die)
        if self.face not in ("top", "bottom"):
            raise ValueError(f"FacePattern.face must be 'top' or 'bottom', got {self.face!r}")
        _require_positive("FacePattern.metal_thickness_um", self.metal_thickness_um)
        _require_name("FacePattern.ground_assignment_name", self.ground_assignment_name)
        _require_name("FacePattern.material", self.material)
        if not self.segments:
            raise ValueError("FacePattern.segments must not be empty")
        if not any(isinstance(segment, (Ground, Trace)) for segment in self.segments):
            raise ValueError("FacePattern requires at least one Ground or Trace segment")


@dataclass(frozen=True, slots=True)
class Q2dSemanticCrossSection:
    """Complete semantic source model for one Q2D case."""

    stack: Stack
    face_patterns: tuple[FacePattern, ...]
    region_name: str = "Vacuum"
    region_material: str = "Vacuum"

    def __post_init__(self) -> None:
        _require_name("Q2dSemanticCrossSection.region_name", self.region_name)
        _require_name("Q2dSemanticCrossSection.region_material", self.region_material)
        if not self.face_patterns:
            raise ValueError("Q2dSemanticCrossSection requires at least one FacePattern")
        die_ids = {element.id for element in self.stack.elements if isinstance(element, Die)}
        has_trace = False
        for pattern in self.face_patterns:
            if pattern.die not in die_ids:
                raise ValueError(
                    f"FacePattern references unknown die {pattern.die!r}; "
                    f"known dies are {sorted(die_ids)}"
                )
            has_trace = has_trace or any(isinstance(segment, Trace) for segment in pattern.segments)
        if not has_trace:
            raise ValueError("Q2dSemanticCrossSection requires at least one Trace")

    def to_payload(self) -> dict[str, Any]:
        """Return the portable JSON payload written into AEDT packages."""

        return {
            "schema_version": "q2d-semantic-cross-section.v1",
            "stack": [_typed_payload(element) for element in self.stack.elements],
            "face_patterns": [
                {
                    "die": pattern.die,
                    "face": pattern.face,
                    "metal_thickness_um": float(pattern.metal_thickness_um),
                    "x0_um": float(pattern.x0_um),
                    "ground_assignment_name": pattern.ground_assignment_name,
                    "material": pattern.material,
                    "segments": [_typed_payload(segment) for segment in pattern.segments],
                }
                for pattern in self.face_patterns
            ],
            "region": {"name": self.region_name, "material": self.region_material},
        }


def make_q2d_same_face_two_trace_cross_section(
    *,
    trace_width_um: float,
    trace_gap_um: float,
    inter_trace_ground_width_um: float,
    upper_ground_clearance_width_um: float,
    flip_chip_gap_height_um: float,
    die_thickness_um: float,
    air_height_um: float,
    ground_width_um: float,
    metal_thickness_um: float,
    trace_names: tuple[str, str] = ("T1", "T2"),
    substrate_material: str = "Silicon",
    conductor_material: str = "pec",
    reference_group: str = "Ground",
) -> Q2dSemanticCrossSection:
    """Build the same-D0 two-trace cross-section beneath D1 ground.

    Both signal traces live on ``D0/top``. ``D1`` remains a material substrate,
    while its ``bottom`` ground plane is either continuous when
    ``upper_ground_clearance_width_um`` is zero or locally removed across one
    centered tagged gap. Numeric dimensions are caller-owned so this public
    helper does not embed private design values.

    Args:
        trace_width_um: Width shared by the two signal traces.
        trace_gap_um: CPW gap surrounding each signal trace.
        inter_trace_ground_width_um: Ground strip between the two CPWs.
        upper_ground_clearance_width_um: Width removed locally from D1 bottom
            ground above the coupled traces; zero keeps the ground continuous.
        flip_chip_gap_height_um: Physical empty spacing between D0 and D1.
        die_thickness_um: Thickness shared by the two public substrate bodies.
        air_height_um: Exterior Vacuum padding below D0 and above D1.
        ground_width_um: Lateral ground extent outside the two CPWs.
        metal_thickness_um: Thickness of the modeled conductor rectangles.
        trace_names: Ordered signal-conductor names.
        substrate_material: AEDT substrate material name.
        conductor_material: AEDT conductor material name.
        reference_group: Shared reference-ground assignment name.

    Returns:
        A semantic cross-section whose payload passes the same-face upper-ground
        topology validator.

    Raises:
        ValueError: A dimension, conductor name, or local-clearance invariant is
            invalid.
    """

    dimensions = {
        "trace_width_um": trace_width_um,
        "trace_gap_um": trace_gap_um,
        "inter_trace_ground_width_um": inter_trace_ground_width_um,
        "flip_chip_gap_height_um": flip_chip_gap_height_um,
        "die_thickness_um": die_thickness_um,
        "air_height_um": air_height_um,
        "ground_width_um": ground_width_um,
        "metal_thickness_um": metal_thickness_um,
    }
    for label, value in dimensions.items():
        _require_positive(label, value)
    clearance_width_um = float(upper_ground_clearance_width_um)
    if not math.isfinite(clearance_width_um) or clearance_width_um < 0.0:
        raise ValueError("upper_ground_clearance_width_um must be finite and non-negative")
    if len(trace_names) != 2 or len(set(trace_names)) != 2:
        raise ValueError("trace_names must contain exactly two distinct conductor names")
    for index, name in enumerate(trace_names):
        _require_name(f"trace_names[{index}]", name)
    _require_name("substrate_material", substrate_material)
    _require_name("conductor_material", conductor_material)
    _require_name("reference_group", reference_group)

    d0_segments: tuple[FaceSegment, ...] = (
        Ground(width_um=ground_width_um),
        Gap(width_um=trace_gap_um),
        Trace(trace_names[0], width_um=trace_width_um),
        Gap(width_um=trace_gap_um),
        Ground(width_um=inter_trace_ground_width_um),
        Gap(width_um=trace_gap_um),
        Trace(trace_names[1], width_um=trace_width_um),
        Gap(width_um=trace_gap_um),
        Ground(width_um=ground_width_um),
    )
    lateral_width_um = sum(segment.width_um for segment in d0_segments)
    upper_side_ground_width_um = (lateral_width_um - clearance_width_um) / 2.0
    if upper_side_ground_width_um <= 0.0:
        raise ValueError(
            "upper_ground_clearance_width_um must leave positive D1 ground metal on both sides"
        )
    x0_um = -lateral_width_um / 2.0

    upper_segments: tuple[FaceSegment, ...] = (
        (Ground(width_um=lateral_width_um),)
        if clearance_width_um == 0.0
        else (
            Ground(width_um=upper_side_ground_width_um),
            Gap(
                width_um=clearance_width_um,
                role="upper_ground_clearance",
            ),
            Ground(width_um=upper_side_ground_width_um),
        )
    )
    cross_section = Q2dSemanticCrossSection(
        stack=Stack(
            (
                Air(height_um=air_height_um),
                Die(id="D0", thickness_um=die_thickness_um, material=substrate_material),
                DieGap(height_um=flip_chip_gap_height_um),
                Die(id="D1", thickness_um=die_thickness_um, material=substrate_material),
                Air(height_um=air_height_um),
            )
        ),
        face_patterns=(
            FacePattern(
                die="D0",
                face="top",
                metal_thickness_um=metal_thickness_um,
                x0_um=x0_um,
                ground_assignment_name=reference_group,
                material=conductor_material,
                segments=d0_segments,
            ),
            FacePattern(
                die="D1",
                face="bottom",
                metal_thickness_um=metal_thickness_um,
                x0_um=x0_um,
                ground_assignment_name=reference_group,
                material=conductor_material,
                segments=upper_segments,
            ),
        ),
    )
    validate_q2d_same_face_upper_ground_clearance_payload(
        cross_section.to_payload(),
        trace_names=trace_names,
    )
    return cross_section


def make_q2d_same_face_single_trace_cross_section(
    *,
    trace_width_um: float,
    trace_gap_um: float,
    upper_ground_clearance_width_um: float,
    flip_chip_gap_height_um: float,
    die_thickness_um: float,
    air_height_um: float,
    ground_width_um: float,
    metal_thickness_um: float,
    trace_name: str = "T1",
    substrate_material: str = "Silicon",
    conductor_material: str = "pec",
    reference_group: str = "Ground",
) -> Q2dSemanticCrossSection:
    """Build one same-face CPW trace beneath D1 ground.

    The signal trace and its lateral CPW ground live on ``D0/top``. ``D1`` is
    retained as a material substrate and carries reference ground on its
    ``bottom`` face. A zero clearance keeps that ground continuous; a positive
    clearance creates one centered tagged opening above the CPW. Numeric
    dimensions remain caller-owned so this helper contains no private defaults.

    Args:
        trace_width_um: Width of the signal trace.
        trace_gap_um: Lateral CPW gap on each side of the trace.
        upper_ground_clearance_width_um: Width removed locally from D1 bottom
            ground above the trace; zero keeps the ground continuous.
        flip_chip_gap_height_um: Physical empty spacing between D0 and D1.
        die_thickness_um: Thickness shared by the two substrate bodies.
        air_height_um: Exterior Vacuum padding below D0 and above D1.
        ground_width_um: Lateral D0 ground extent outside each CPW gap.
        metal_thickness_um: Thickness of the modeled conductor rectangles.
        trace_name: Signal-conductor assignment name.
        substrate_material: AEDT substrate material name.
        conductor_material: AEDT conductor material name.
        reference_group: Shared reference-ground assignment name.

    Returns:
        A semantic cross-section satisfying the single-reference topology.

    Raises:
        ValueError: A dimension, name, or centered-clearance invariant is
            invalid.
    """

    dimensions = {
        "trace_width_um": trace_width_um,
        "trace_gap_um": trace_gap_um,
        "flip_chip_gap_height_um": flip_chip_gap_height_um,
        "die_thickness_um": die_thickness_um,
        "air_height_um": air_height_um,
        "ground_width_um": ground_width_um,
        "metal_thickness_um": metal_thickness_um,
    }
    for label, value in dimensions.items():
        _require_positive(label, value)
    clearance_width_um = float(upper_ground_clearance_width_um)
    if not math.isfinite(clearance_width_um) or clearance_width_um < 0.0:
        raise ValueError("upper_ground_clearance_width_um must be finite and non-negative")
    _require_name("trace_name", trace_name)
    _require_name("substrate_material", substrate_material)
    _require_name("conductor_material", conductor_material)
    _require_name("reference_group", reference_group)

    d0_segments: tuple[FaceSegment, ...] = (
        Ground(width_um=ground_width_um),
        Gap(width_um=trace_gap_um),
        Trace(trace_name, width_um=trace_width_um),
        Gap(width_um=trace_gap_um),
        Ground(width_um=ground_width_um),
    )
    lateral_width_um = sum(segment.width_um for segment in d0_segments)
    upper_side_ground_width_um = (lateral_width_um - clearance_width_um) / 2.0
    if upper_side_ground_width_um <= 0.0:
        raise ValueError(
            "upper_ground_clearance_width_um must leave positive D1 ground metal on both sides"
        )
    x0_um = -lateral_width_um / 2.0

    upper_segments: tuple[FaceSegment, ...] = (
        (Ground(width_um=lateral_width_um),)
        if clearance_width_um == 0.0
        else (
            Ground(width_um=upper_side_ground_width_um),
            Gap(
                width_um=clearance_width_um,
                role="upper_ground_clearance",
            ),
            Ground(width_um=upper_side_ground_width_um),
        )
    )
    cross_section = Q2dSemanticCrossSection(
        stack=Stack(
            (
                Air(height_um=air_height_um),
                Die(id="D0", thickness_um=die_thickness_um, material=substrate_material),
                DieGap(height_um=flip_chip_gap_height_um),
                Die(id="D1", thickness_um=die_thickness_um, material=substrate_material),
                Air(height_um=air_height_um),
            )
        ),
        face_patterns=(
            FacePattern(
                die="D0",
                face="top",
                metal_thickness_um=metal_thickness_um,
                x0_um=x0_um,
                ground_assignment_name=reference_group,
                material=conductor_material,
                segments=d0_segments,
            ),
            FacePattern(
                die="D1",
                face="bottom",
                metal_thickness_um=metal_thickness_um,
                x0_um=x0_um,
                ground_assignment_name=reference_group,
                material=conductor_material,
                segments=upper_segments,
            ),
        ),
    )
    validate_q2d_single_reference_upper_ground_clearance_payload(
        cross_section.to_payload(),
        trace_name=trace_name,
    )
    return cross_section


def validate_q2d_single_reference_upper_ground_clearance_payload(
    payload: Any,
    *,
    trace_name: str = "T1",
) -> dict[str, Any]:
    """Validate and summarize one isolated same-face CPW reference case.

    The contract is deliberately distinct from the two-trace coupled topology:
    it requires exactly one ``D0/top`` trace, an ordinary ground-gap-trace-gap-
    ground CPW pattern, retained D1 substrate, and either a continuous
    ``D1/bottom`` reference ground or one centered tagged local clearance.

    Args:
        payload: Decoded ``q2d-semantic-cross-section.v1`` payload.
        trace_name: Expected signal-conductor name.

    Returns:
        A normalized single-reference topology summary.

    Raises:
        ValueError: The payload does not implement the isolated CPW topology.
    """

    validated = validate_q2d_cross_section_payload(payload)
    expected_trace_name = _require_name("trace_name", trace_name)

    stack = validated["stack"]
    die_rows = [element for element in stack if element.get("kind") == "die"]
    if [element.get("id") for element in die_rows] != ["D0", "D1"]:
        raise ValueError(
            "single-reference clearance topology requires exactly D0 then D1 substrates"
        )
    d0_index = stack.index(die_rows[0])
    d1_index = stack.index(die_rows[1])
    if not any(element.get("kind") == "die_gap" for element in stack[d0_index + 1 : d1_index]):
        raise ValueError("single-reference clearance topology requires a DieGap between D0 and D1")

    if len(validated["face_patterns"]) != 2:
        raise ValueError(
            "single-reference clearance topology requires only one D0/top CPW pattern "
            "and one D1/bottom ground pattern"
        )
    resonator_patterns = [
        pattern
        for pattern in validated["face_patterns"]
        if pattern.get("die") == "D0" and pattern.get("face") == "top"
    ]
    upper_patterns = [
        pattern
        for pattern in validated["face_patterns"]
        if pattern.get("die") == "D1" and pattern.get("face") == "bottom"
    ]
    if len(resonator_patterns) != 1 or len(upper_patterns) != 1:
        raise ValueError(
            "single-reference clearance topology requires D0/top CPW and D1/bottom ground"
        )

    resonator_pattern = resonator_patterns[0]
    upper_pattern = upper_patterns[0]
    resonator_segments = resonator_pattern["segments"]
    upper_segments = upper_pattern["segments"]
    if [segment.get("kind") for segment in resonator_segments] != [
        "ground",
        "gap",
        "trace",
        "gap",
        "ground",
    ]:
        raise ValueError("single-reference D0/top pattern must be Ground-Gap-Trace-Gap-Ground")
    traces = [segment for segment in resonator_segments if segment.get("kind") == "trace"]
    if [segment.get("name") for segment in traces] != [expected_trace_name]:
        raise ValueError(
            "single-reference clearance topology requires exactly one ordered trace "
            f"{expected_trace_name!r} on D0/top"
        )
    lateral_gaps = [segment for segment in resonator_segments if segment.get("kind") == "gap"]
    if any(segment.get("role", "lateral_spacing") != "lateral_spacing" for segment in lateral_gaps):
        raise ValueError("single-reference D0/top gaps must be lateral_spacing gaps")
    if not math.isclose(
        float(lateral_gaps[0]["width_um"]),
        float(lateral_gaps[1]["width_um"]),
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ValueError("single-reference CPW gaps must have equal width")
    lateral_grounds = [segment for segment in resonator_segments if segment.get("kind") == "ground"]
    if not math.isclose(
        float(lateral_grounds[0]["width_um"]),
        float(lateral_grounds[1]["width_um"]),
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ValueError("single-reference CPW side grounds must have equal width")

    upper_kinds = [segment.get("kind") for segment in upper_segments]
    continuous_upper_ground = upper_kinds == ["ground"]
    if not continuous_upper_ground and upper_kinds != ["ground", "gap", "ground"]:
        raise ValueError(
            "single-reference D1/bottom pattern must be Ground or Ground-Clearance-Ground"
        )
    clearance = None if continuous_upper_ground else upper_segments[1]
    if clearance is not None and clearance.get("role") != "upper_ground_clearance":
        raise ValueError("single-reference D1/bottom gap requires role='upper_ground_clearance'")

    resonator_x0 = float(resonator_pattern.get("x0_um", 0.0))
    upper_x0 = float(upper_pattern.get("x0_um", 0.0))
    resonator_width = sum(float(segment["width_um"]) for segment in resonator_segments)
    upper_width = sum(float(segment["width_um"]) for segment in upper_segments)
    if not math.isclose(resonator_x0, upper_x0, rel_tol=0.0, abs_tol=1e-12) or not math.isclose(
        resonator_width,
        upper_width,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ValueError(
            "D1/bottom ground pattern must cover the full D0/top modeled lateral extent"
        )
    if clearance is not None:
        clearance_center = (
            upper_x0 + float(upper_segments[0]["width_um"]) + float(clearance["width_um"]) / 2.0
        )
        pattern_center = resonator_x0 + resonator_width / 2.0
        if not math.isclose(
            clearance_center,
            pattern_center,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError("single-reference upper-ground clearance must be centered")

    reference_groups = {
        str(pattern.get("ground_assignment_name") or "Ground")
        for pattern in validated["face_patterns"]
    }
    if len(reference_groups) != 1:
        raise ValueError(
            "single-reference clearance topology requires one shared reference-ground group"
        )

    return {
        "schema_version": (
            "q2d-single-reference-continuous-upper-ground.v1"
            if continuous_upper_ground
            else "q2d-single-reference-upper-ground-clearance.v1"
        ),
        "resonator_die": "D0",
        "resonator_face": "top",
        "trace_names": [expected_trace_name],
        "upper_die": "D1",
        "upper_die_substrate_present": True,
        "upper_ground_face": "bottom",
        "upper_ground_clearance_width_um": (
            0.0 if clearance is None else float(clearance["width_um"])
        ),
        "upper_ground_clearance_alignment": ("not_applicable" if clearance is None else "centered"),
        "upper_ground_metal_policy": (
            "continuous_over_full_modeled_lateral_extent"
            if clearance is None
            else "removed_only_within_local_clearance"
        ),
        "reference_group": reference_groups.pop(),
    }


def validate_q2d_same_face_upper_ground_clearance_payload(
    payload: Any,
    *,
    trace_names: tuple[str, str] = ("T1", "T2"),
) -> dict[str, Any]:
    """Validate and summarize the intrinsic-Purcell Q2D topology contract.

    This check is intentionally stronger than generic cross-section validation.
    It rejects the earlier opposing-face geometry, requires both signals on
    ``D0/top``, preserves ``D1`` as a substrate, and accepts either a continuous
    D1 reference ground or one local tagged clearance.

    Args:
        payload: Decoded ``q2d-semantic-cross-section.v1`` payload.
        trace_names: Expected ordered signal-conductor names.

    Returns:
        A normalized topology summary suitable for result-artifact metadata.

    Raises:
        ValueError: The payload does not implement the required topology.
    """

    validated = validate_q2d_cross_section_payload(payload)
    if len(trace_names) != 2 or len(set(trace_names)) != 2:
        raise ValueError("trace_names must contain exactly two distinct conductor names")

    stack = validated["stack"]
    die_indices = {
        element["id"]: index for index, element in enumerate(stack) if element.get("kind") == "die"
    }
    if "D0" not in die_indices or "D1" not in die_indices:
        raise ValueError("same-face clearance topology requires D0 and D1 substrates")
    if die_indices["D0"] >= die_indices["D1"]:
        raise ValueError("same-face clearance topology requires D1 above D0")
    between_dies = stack[die_indices["D0"] + 1 : die_indices["D1"]]
    if not any(element.get("kind") == "die_gap" for element in between_dies):
        raise ValueError("same-face clearance topology requires a DieGap between D0 and D1")

    trace_locations: dict[str, tuple[str, str]] = {}
    upper_patterns = []
    resonator_patterns = []
    reference_groups = set()
    for pattern in validated["face_patterns"]:
        reference_groups.add(str(pattern.get("ground_assignment_name") or "Ground"))
        for segment in pattern["segments"]:
            if segment.get("kind") == "trace":
                name = str(segment["name"])
                if name in trace_locations:
                    raise ValueError(f"duplicate Q2D trace name in face patterns: {name!r}")
                trace_locations[name] = (str(pattern["die"]), str(pattern["face"]))
        if pattern.get("die") == "D1" and pattern.get("face") == "bottom":
            upper_patterns.append(pattern)
        if pattern.get("die") == "D0" and pattern.get("face") == "top":
            resonator_patterns.append(pattern)

    if tuple(trace_locations) != trace_names:
        raise ValueError(
            "same-face clearance topology requires ordered traces "
            f"{trace_names!r}, got {tuple(trace_locations)!r}"
        )
    wrong_face = {
        name: location for name, location in trace_locations.items() if location != ("D0", "top")
    }
    if wrong_face:
        raise ValueError(
            f"same-face clearance topology requires every trace on D0/top; got {wrong_face}"
        )
    if len(validated["face_patterns"]) != 2 or len(resonator_patterns) != 1:
        raise ValueError(
            "same-face clearance topology requires only one D0/top trace pattern "
            "and one D1/bottom ground pattern"
        )
    if len(upper_patterns) != 1:
        raise ValueError("same-face clearance topology requires one D1/bottom ground pattern")

    resonator_pattern = resonator_patterns[0]
    upper_pattern = upper_patterns[0]
    upper_segments = upper_pattern["segments"]
    resonator_x0 = float(resonator_pattern.get("x0_um", 0.0))
    upper_x0 = float(upper_pattern.get("x0_um", 0.0))
    resonator_x1 = resonator_x0 + sum(
        float(segment["width_um"]) for segment in resonator_pattern["segments"]
    )
    upper_x1 = upper_x0 + sum(float(segment["width_um"]) for segment in upper_segments)
    if not math.isclose(resonator_x0, upper_x0, rel_tol=0.0, abs_tol=1e-12) or not math.isclose(
        resonator_x1,
        upper_x1,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ValueError(
            "D1/bottom ground pattern must cover the full D0/top modeled lateral extent"
        )
    continuous_upper_ground = len(upper_segments) == 1 and upper_segments[0].get("kind") == "ground"
    clearances = [
        (index, segment)
        for index, segment in enumerate(upper_segments)
        if segment.get("kind") == "gap" and segment.get("role") == "upper_ground_clearance"
    ]
    if not continuous_upper_ground and len(clearances) != 1:
        raise ValueError(
            "D1/bottom requires one continuous Ground or exactly one Gap with "
            "role='upper_ground_clearance'"
        )
    clearance_index, clearance = (-1, None) if continuous_upper_ground else clearances[0]
    other_gaps = [
        segment
        for index, segment in enumerate(upper_segments)
        if segment.get("kind") == "gap" and index != clearance_index
    ]
    if other_gaps:
        raise ValueError("D1/bottom ground metal may be removed only within the clearance")
    if any(segment.get("kind") == "trace" for segment in upper_segments):
        raise ValueError("D1/bottom upper-ground pattern must not contain signal traces")
    if clearance is not None:
        if not any(segment.get("kind") == "ground" for segment in upper_segments[:clearance_index]):
            raise ValueError("upper-ground clearance must retain ground metal on its left")
        if not any(
            segment.get("kind") == "ground" for segment in upper_segments[clearance_index + 1 :]
        ):
            raise ValueError("upper-ground clearance must retain ground metal on its right")
    if len(reference_groups) != 1:
        raise ValueError("same-face clearance topology requires one shared reference-ground group")

    return {
        "schema_version": (
            "q2d-same-face-continuous-upper-ground.v1"
            if continuous_upper_ground
            else "q2d-same-face-upper-ground-clearance.v1"
        ),
        "resonator_die": "D0",
        "resonator_face": "top",
        "trace_names": list(trace_names),
        "upper_die": "D1",
        "upper_die_substrate_present": True,
        "upper_ground_face": "bottom",
        "upper_ground_clearance_width_um": (
            0.0 if clearance is None else float(clearance["width_um"])
        ),
        "upper_ground_metal_policy": (
            "continuous_over_full_modeled_lateral_extent"
            if clearance is None
            else "removed_only_within_local_clearance"
        ),
        "reference_group": reference_groups.pop(),
    }


def validate_q2d_cross_section_payload(payload: Any) -> dict[str, Any]:
    """Validate the semantic Q2D JSON sidecar shape.

    Args:
        payload: Decoded JSON object to validate.

    Returns:
        The same payload when it satisfies the v1 semantic contract.

    Raises:
        ValueError: The payload is missing required semantic fields.
    """

    if not isinstance(payload, dict):
        raise ValueError("Q2D semantic cross-section sidecar must be a JSON object")
    if payload.get("schema_version") != "q2d-semantic-cross-section.v1":
        raise ValueError("Q2D semantic cross-section requires schema_version v1")
    stack = payload.get("stack")
    face_patterns = payload.get("face_patterns")
    if not isinstance(stack, list) or not stack:
        raise ValueError("Q2D semantic cross-section requires a non-empty stack list")
    if not isinstance(face_patterns, list) or not face_patterns:
        raise ValueError("Q2D semantic cross-section requires a non-empty face_patterns list")
    die_ids: list[str] = []
    for index, element in enumerate(stack):
        if not isinstance(element, dict):
            raise ValueError(f"stack[{index}] must be an object")
        kind = element.get("kind")
        if kind == "air":
            _require_positive(f"stack[{index}].height_um", element.get("height_um"))
            if index not in {0, len(stack) - 1}:
                raise ValueError("Air is only allowed at stack edges")
        elif kind == "die_gap":
            _require_positive(f"stack[{index}].height_um", element.get("height_um"))
        elif kind == "die":
            die_id = _require_name(f"stack[{index}].id", element.get("id"))
            _require_positive(f"stack[{index}].thickness_um", element.get("thickness_um"))
            _require_name(f"stack[{index}].material", element.get("material"))
            die_ids.append(die_id)
        else:
            raise ValueError(f"Unsupported stack element kind: {kind!r}")
    if not die_ids:
        raise ValueError("Q2D semantic cross-section stack requires at least one die")
    duplicates = sorted({die_id for die_id in die_ids if die_ids.count(die_id) > 1})
    if duplicates:
        raise ValueError(f"Q2D semantic cross-section die ids must be unique: {duplicates}")
    has_trace = False
    for index, pattern in enumerate(face_patterns):
        if not isinstance(pattern, dict):
            raise ValueError(f"face_patterns[{index}] must be an object")
        die = _require_name(f"face_patterns[{index}].die", pattern.get("die"))
        if die not in die_ids:
            raise ValueError(f"face_patterns[{index}] references unknown die {die!r}")
        if pattern.get("face") not in {"top", "bottom"}:
            raise ValueError(f"face_patterns[{index}].face must be top or bottom")
        _require_positive(
            f"face_patterns[{index}].metal_thickness_um",
            pattern.get("metal_thickness_um"),
        )
        segments = pattern.get("segments")
        if not isinstance(segments, list) or not segments:
            raise ValueError(f"face_patterns[{index}].segments must be a non-empty list")
        for segment_index, segment in enumerate(segments):
            if not isinstance(segment, dict):
                raise ValueError(f"face_patterns[{index}].segments[{segment_index}] must be object")
            kind = segment.get("kind")
            if kind in {"ground", "gap"}:
                _require_positive(
                    f"face_patterns[{index}].segments[{segment_index}].width_um",
                    segment.get("width_um"),
                )
                if kind == "gap" and segment.get("role", "lateral_spacing") not in {
                    "lateral_spacing",
                    "upper_ground_clearance",
                }:
                    raise ValueError(f"Unsupported face gap role: {segment.get('role')!r}")
            elif kind == "trace":
                has_trace = True
                _require_name(
                    f"face_patterns[{index}].segments[{segment_index}].name",
                    segment.get("name"),
                )
                _require_positive(
                    f"face_patterns[{index}].segments[{segment_index}].width_um",
                    segment.get("width_um"),
                )
            else:
                raise ValueError(f"Unsupported face segment kind: {kind!r}")
    if not has_trace:
        raise ValueError("Q2D semantic cross-section requires at least one trace segment")
    return payload


def load_q2d_raw_sweep_result(
    run_root: str | Path,
    parameter_space: ParameterSpace,
    recipe_id: str = "q2d",
) -> Q2dRawSweepResult:
    """Load raw matrix exports for a full Q2D parameter sweep.

    The loader follows ``ParameterSpace`` order and keeps this layer limited to
    AEDT-exported matrix entries. CSV output is explicit through
    ``Q2dRawSweepResult.write_csv()`` so notebook cells can separate loading
    from publishing analysis artifacts.
    """

    return Q2dRawSweepResult(
        run_root=Path(run_root),
        parameter_space=parameter_space,
        recipe_id=recipe_id,
    )


def load_q2d_raw_point_result(
    result_dir: str | Path,
    *,
    point_id: str,
    point_slug: str,
    coords: Mapping[str, Any] | None = None,
    required_sources: Sequence[Q2dMatrixSource] | None = None,
) -> Q2dRawPoint:
    """Load selected required Q2D matrix exports for one solved point.

    Args:
        result_dir: Directory containing AEDT Maxwell and coupling CSV exports.
        point_id: Stable parameter-space identity for the point.
        point_slug: Stable filesystem identity for the point.
        coords: Optional parameter coordinates copied onto each parsed row.
        required_sources: Matrix sources to load. The default preserves the
            four-export raw sweep contract; callers that consume only Maxwell
            L/C may explicitly request ``cg_maxwell`` and ``rl_maxwell``.

    Returns:
        A strict raw-point view over all parsed matrix entries.

    Raises:
        FileNotFoundError: A required matrix export is absent.
        ValueError: A matrix export is empty or has no parseable entries.
    """

    result_dir = Path(result_dir)
    coordinates = dict(coords or {})
    sources = tuple(_Q2D_RAW_MATRIX_FILES) if required_sources is None else tuple(required_sources)
    if not sources:
        raise ValueError("required_sources must contain at least one Q2D matrix source")
    if len(sources) != len(set(sources)):
        raise ValueError("required_sources must not contain duplicate Q2D matrix sources")
    unsupported_sources = sorted(set(sources) - set(_Q2D_RAW_MATRIX_FILES))
    if unsupported_sources:
        raise ValueError(f"Unsupported Q2D matrix sources: {unsupported_sources}")
    point_rows: list[dict[str, Any]] = []
    for source in sources:
        file_name = _Q2D_RAW_MATRIX_FILES[source]
        matrix_path = result_dir / file_name
        if not matrix_path.exists():
            raise FileNotFoundError(f"Missing Q2D matrix export: {matrix_path}")
        if matrix_path.stat().st_size <= 0:
            raise ValueError(f"Q2D matrix export is empty: {matrix_path}")
        parsed = _parse_q2d_matrix_csv(matrix_path, point_slug=point_slug)
        if not parsed:
            raise ValueError(f"Q2D matrix export did not contain parsed entries: {matrix_path}")
        for row in parsed:
            enriched = {
                "parameter_id": point_id,
                **coordinates,
                **row,
            }
            if row.get("value") is not None:
                if source.endswith("couple"):
                    enriched["value_si"] = float(row["value"])
                elif row.get("quantity") in {"C", "L"}:
                    enriched["value_si"] = _si_per_meter(
                        row["value"],
                        row.get("unit"),
                        str(row["quantity"]),
                    )
            point_rows.append(enriched)
    return Q2dRawPoint(
        point_id=point_id,
        point_slug=point_slug,
        coords=coordinates,
        matrix_rows=point_rows,
    )


@dataclass(frozen=True, slots=True)
class Q2dMatrixElement:
    """Typed index into a parsed matrix export row."""

    source: Q2dMatrixSource
    quantity: Q2dMatrixQuantity
    row: str
    column: str


class Q2dFormula:
    """Minimal protocol-like contract for derived formulas."""

    name: str
    inputs: tuple[Q2dMatrixElement, ...]
    outputs: tuple[str, ...]

    def evaluate(self, point: Q2dRawPoint) -> dict[str, float]:
        raise NotImplementedError

    def default_plots(
        self,
        view: Q2dResultView,
    ) -> tuple[Q2dLinePlot | Q2dHeatMap | Q2dFacetLineGrid, ...]:
        return ()

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "inputs": [asdict(element) for element in self.inputs],
            "outputs": list(self.outputs),
        }


@dataclass(frozen=True, slots=True)
class Q2dLinePlot:
    y: str | tuple[str, ...]
    x: str | None = None
    title: str | None = None

    def render(self, view: Q2dResultView) -> Any:
        go = _plotly_graph_objects()
        x = self.x or (view.axes[0] if view.axes else None)
        if x is None:
            return
        fig = go.Figure()
        xs = [row.get(x) for row in view.rows]
        y_fields = (self.y,) if isinstance(self.y, str) else tuple(self.y)
        for y in y_fields:
            ys = [row.get(y) for row in view.rows]
            if xs and any(value is not None for value in ys):
                fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines+markers", name=y))
        fig.update_layout(title=self.title, xaxis_title=x)
        fig.show()


@dataclass(frozen=True, slots=True)
class Q2dHeatMap:
    z: str
    x: str | None = None
    y: str | None = None
    title: str | None = None

    def render(self, view: Q2dResultView) -> None:
        go = _plotly_graph_objects()
        x = self.x or (view.axes[0] if len(view.axes) >= 1 else None)
        y = self.y or (view.axes[1] if len(view.axes) >= 2 else None)
        if not view.rows or x is None or y is None:
            return
        xs = sorted({row.get(x) for row in view.rows if x in row})
        ys = sorted({row.get(y) for row in view.rows if y in row})
        if not xs or not ys:
            return
        heat = [[None for _ in xs] for _ in ys]
        for row in view.rows:
            xi = xs.index(row.get(x))
            yi = ys.index(row.get(y))
            heat[yi][xi] = float(row.get(self.z, 0.0))
        fig = go.Figure(data=go.Heatmap(x=xs, y=ys, z=heat, colorbar={"title": self.z}))
        fig.update_layout(title=self.title, xaxis_title=x, yaxis_title=y)
        fig.show()


@dataclass(frozen=True, slots=True)
class Q2dFacetLineGrid:
    x: str
    y: tuple[tuple[str, str], ...]
    facet_col: str
    color: str
    line_dash: str
    line_dash_map: Mapping[Any, str]
    title: str | None = None
    x_title: str | None = None
    color_title: str | None = None
    facet_col_title: str = "{value}"
    shared_y: bool = True

    def render(self, view: Q2dResultView) -> None:
        go = _plotly_graph_objects()
        colors = _plotly_colors()
        make_subplots = _plotly_subplots().make_subplots
        facet_values = _sorted_unique(row.get(self.facet_col) for row in view.rows)
        color_values = _sorted_unique(row.get(self.color) for row in view.rows)
        dash_values = _sorted_unique(row.get(self.line_dash) for row in view.rows)
        if not view.rows or not self.y or not facet_values:
            return
        color_numbers = _numeric_values(color_values, self.color)
        color_min = min(color_numbers)
        color_max = max(color_numbers)
        subplot_titles = tuple(
            self.facet_col_title.format(value=value) if row == 0 else ""
            for row in range(len(self.y))
            for value in facet_values
        )
        fig = make_subplots(
            rows=len(self.y),
            cols=len(facet_values),
            shared_yaxes=self.shared_y,
            subplot_titles=subplot_titles,
            horizontal_spacing=0.08,
            vertical_spacing=0.15,
        )
        color_by_value = {
            value: colors.sample_colorscale(
                "Viridis",
                [_normalized(number, color_min, color_max)],
            )[0]
            for value, number in zip(color_values, color_numbers, strict=True)
        }
        for row_index, (metric, label) in enumerate(self.y, start=1):
            for col_index, facet_value in enumerate(facet_values, start=1):
                for color_value in color_values:
                    for dash_value in dash_values:
                        rows = sorted(
                            (
                                row
                                for row in view.rows
                                if row.get(self.facet_col) == facet_value
                                and row.get(self.color) == color_value
                                and row.get(self.line_dash) == dash_value
                            ),
                            key=lambda row: row.get(self.x),
                        )
                        if not rows:
                            continue
                        fig.add_trace(
                            go.Scatter(
                                x=[row.get(self.x) for row in rows],
                                y=[row.get(metric) for row in rows],
                                mode="lines",
                                name=f"{label}, {self.color}={_format_value(color_value)}",
                                line={
                                    "color": color_by_value[color_value],
                                    "dash": self.line_dash_map.get(dash_value, "solid"),
                                },
                                showlegend=False,
                            ),
                            row=row_index,
                            col=col_index,
                        )
            fig.update_yaxes(
                title_text=label,
                title_standoff=14,
                automargin=True,
                row=row_index,
                col=1,
            )
        if self.x_title:
            for col_index in range(1, len(facet_values) + 1):
                fig.update_xaxes(
                    title_text=self.x_title,
                    title_standoff=12,
                    automargin=True,
                    row=len(self.y),
                    col=col_index,
                )
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker={
                    "color": [color_min, color_max],
                    "colorscale": "Viridis",
                    "cmin": color_min,
                    "cmax": color_max,
                    "showscale": True,
                    "colorbar": {
                        "title": self.color_title or self.color,
                        "x": 1.015,
                        "y": 0.47,
                        "len": 0.72,
                        "thickness": 18,
                    },
                },
                showlegend=False,
            ),
            row=1,
            col=len(facet_values),
        )
        for dash_value in dash_values:
            fig.add_trace(
                go.Scatter(
                    x=[None],
                    y=[None],
                    mode="lines",
                    name=_format_value(dash_value),
                    line={"dash": self.line_dash_map.get(dash_value, "solid"), "color": "black"},
                    showlegend=True,
                ),
                row=1,
                col=1,
            )
        fig.update_layout(
            title={"text": self.title, "x": 0.02, "xanchor": "left"},
            width=max(1600, 460 * len(facet_values) + 360),
            height=max(1050, 300 * len(self.y) + 220),
            margin={"l": 130, "r": 300, "t": 160, "b": 115},
            legend={
                "orientation": "h",
                "x": 0.5,
                "xanchor": "center",
                "y": 1.08,
                "yanchor": "bottom",
                "title": {"text": self.line_dash},
            },
        )
        fig.show()
        return fig


def _plotly_graph_objects() -> Any:
    return _plotly_module("plotly.graph_objects")


def _plotly_colors() -> Any:
    return _plotly_module("plotly.colors")


def _plotly_subplots() -> Any:
    return _plotly_module("plotly.subplots")


def _plotly_module(name: str) -> Any:
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as exc:
        if exc.name and not exc.name.startswith("plotly"):
            raise
        raise ModuleNotFoundError(
            "Plotly is required for Q2D visualization. Run `uv sync --all-extras` "
            "or sync the `ecosystem-dev` dependency group."
        ) from exc


class Q2dResultView:
    """Materialized result rows for one sub-sweep.

    The view keeps query order from the original ``ParameterSpace`` call and
    handles optional CSV/plot output behavior for derived rows.
    """

    def __init__(
        self,
        rows: list[dict[str, Any]],
        *,
        axes: tuple[str, ...],
        coordinate_columns: tuple[str, ...] = (),
        fixed_coordinates: Mapping[str, Any] | None = None,
        formulas: tuple[Q2dFormula, ...] = (),
        default_csv: Path | None = None,
    ) -> None:
        self.rows = list(rows)
        self.axes = tuple(axes)
        self.coordinate_columns = tuple(coordinate_columns)
        self.fixed_coordinates = dict(fixed_coordinates or {})
        self.formulas = tuple(formulas)
        self.default_csv = default_csv

    @property
    def metrics(self) -> tuple[str, ...]:
        if not self.rows:
            return ()
        formula_outputs = [
            output
            for formula in self.formulas
            for output in formula.outputs
            if output in self.rows[0]
        ]
        if formula_outputs:
            return tuple(formula_outputs)
        reserved = {
            "point_slug",
            "point_id",
            "point_key",
            "parameter_id",
            "run_root",
            *self.axes,
            *self.coordinate_columns,
        }
        return tuple(key for key in self.rows[0] if key not in reserved)

    def write_csv(self, path: str | Path | None = None) -> Path:
        path = Path(path or self.default_csv) if path is not None or self.default_csv else None
        if path is None:
            raise ValueError("CSV path is required when no default is configured")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=_sorted_fieldnames(self.rows))
            writer.writeheader()
            writer.writerows(self.rows)
        return path

    def where(self, **filters: Any) -> Q2dResultView:
        rows = [
            row
            for row in self.rows
            if all(_matches_filter(row.get(key), condition) for key, condition in filters.items())
        ]
        return Q2dResultView(
            rows,
            axes=self.axes,
            coordinate_columns=self.coordinate_columns,
            fixed_coordinates=self.fixed_coordinates,
            formulas=self.formulas,
            default_csv=self.default_csv,
        )

    def show(self, *plots: Q2dLinePlot | Q2dHeatMap | Q2dFacetLineGrid) -> None:
        """Render provided plots or delegate to formula defaults.

        Explicit plot specs always render. Automatic plotting is handled by
        ``show_all_results`` so formulas own their default visualizations.
        """

        if not plots:
            self.show_all_results()
            return
        for plot in plots:
            plot.render(self)

    def show_all_results(self) -> dict[str, Any]:
        if len(self.axes) != 1:
            return {
                "axes": list(self.axes),
                "rows": len(self.rows),
                "metrics": list(self.metrics),
            }
        rendered = []
        for formula in self.formulas:
            for plot in formula.default_plots(self):
                plot.render(self)
                rendered.append(type(plot).__name__)
        return {
            "axes": list(self.axes),
            "rows": len(self.rows),
            "metrics": list(self.metrics),
            "plots": rendered,
        }


class Q2dRawPoint:
    """One sweep point with all parsed matrix rows."""

    def __init__(
        self,
        point_id: str,
        point_slug: str,
        coords: Mapping[str, Any],
        matrix_rows: Sequence[dict[str, Any]],
    ) -> None:
        self.point_id = point_id
        self.point_slug = point_slug
        self.coords = dict(coords)
        self._matrix_rows = list(matrix_rows)

    def matrix_table(self) -> list[dict[str, Any]]:
        """Return the long-format matrix rows for this point."""

        return list(self._matrix_rows)

    def value(self, element: Q2dMatrixElement) -> float:
        rows = self._matching_rows(element)
        if not rows:
            raise KeyError(f"No matrix entry for {element!r}")
        if len(rows) != 1:
            raise KeyError(f"Ambiguous matrix entry for {element!r}")
        return float(rows[0]["value"])

    def value_si(self, element: Q2dMatrixElement) -> float:
        rows = self._matching_rows(element)
        if not rows:
            raise KeyError(f"No matrix entry for {element!r}")
        row = rows[0]
        if element.source.endswith("couple"):
            return float(row["value"])
        return _si_per_meter(row["value"], row.get("unit"), element.quantity)

    def _matching_rows(self, element: Q2dMatrixElement) -> list[dict[str, Any]]:
        return [
            row
            for row in self._matrix_rows
            if row.get("matrix_source") == element.source
            and row.get("quantity") == element.quantity
            and row.get("row_terminal") == element.row
            and row.get("column_terminal") == element.column
        ]


class Q2dImpedanceFormula(Q2dFormula):
    """Built-in self/mutual impedance helpers."""

    def __init__(
        self,
        name: str,
        inputs: tuple[Q2dMatrixElement, ...],
        outputs: tuple[str, ...],
        evaluator: Callable[[Q2dRawPoint], dict[str, float]],
        parameters: Mapping[str, Any] | None = None,
    ) -> None:
        self.name = name
        self.inputs = inputs
        self.outputs = outputs
        self._evaluate = evaluator
        self.parameters = dict(parameters or {})

    def evaluate(self, point: Q2dRawPoint) -> dict[str, float]:
        return self._evaluate(point)

    def default_plots(self, view: Q2dResultView) -> tuple[Q2dLinePlot | Q2dHeatMap, ...]:
        if len(view.axes) != 1:
            return ()
        return (Q2dLinePlot(y=self.outputs, title=self.name),)

    def describe(self) -> dict[str, Any]:
        payload = super().describe()
        payload["parameters"] = self.parameters
        return payload

    @classmethod
    def self(
        cls,
        name: str = "zo",
        trace_names: tuple[str, ...] = ("T1", "T2"),
    ) -> Q2dImpedanceFormula:
        """Return ``sqrt(Lii/Cii)`` formula rows."""

        def _evaluate(point: Q2dRawPoint) -> dict[str, float]:
            rows: dict[str, float] = {}
            for trace_name in trace_names:
                denominator = point.value_si(
                    Q2dMatrixElement("cg_maxwell", "C", trace_name, trace_name),
                )
                if denominator <= 0.0:
                    raise ValueError(
                        f"Cannot compute self impedance for {trace_name}: denominator <= 0"
                    )
                numerator = point.value_si(
                    Q2dMatrixElement("rl_maxwell", "L", trace_name, trace_name),
                )
                rows[f"{name}_{trace_name}_ohm"] = math.sqrt(numerator / denominator)
            return rows

        inputs = tuple(
            element
            for trace_name in trace_names
            for element in (
                Q2dMatrixElement("rl_maxwell", "L", trace_name, trace_name),
                Q2dMatrixElement("cg_maxwell", "C", trace_name, trace_name),
            )
        )

        return cls(
            name=name,
            inputs=inputs,
            outputs=tuple(f"{name}_{trace_name}_ohm" for trace_name in trace_names),
            evaluator=_evaluate,
            parameters={"kind": "self_impedance", "trace_names": list(trace_names)},
        )

    @classmethod
    def mutual(
        cls,
        name: str = "zm",
        trace_pair: tuple[str, str] = ("T1", "T2"),
    ) -> Q2dImpedanceFormula:
        """Return ``sqrt(Lij/(-Cij))`` formula rows."""

        if len(trace_pair) != 2:
            raise ValueError("trace_pair must be two terminal names")
        a, b = trace_pair

        def _evaluate(point: Q2dRawPoint) -> dict[str, float]:
            denominator = -point.value_si(Q2dMatrixElement("cg_maxwell", "C", a, b))
            if denominator <= 0.0:
                raise ValueError(f"Cannot compute mutual impedance for {a},{b}: denominator <= 0")
            numerator = point.value_si(Q2dMatrixElement("rl_maxwell", "L", a, b))
            return {f"{name}_{a}_{b}_ohm": math.sqrt(numerator / denominator)}

        return cls(
            name=name,
            inputs=(
                Q2dMatrixElement("rl_maxwell", "L", a, b),
                Q2dMatrixElement("cg_maxwell", "C", a, b),
            ),
            outputs=(f"{name}_{a}_{b}_ohm",),
            evaluator=_evaluate,
            parameters={
                "kind": "mutual_impedance",
                "trace_pair": list(trace_pair),
                "capacitance_scale": -1,
            },
        )


class Q2dRawSweepResult:
    """Read-only raw Q2D results with ParameterSpace-style point views."""

    def __init__(
        self,
        run_root: str | Path,
        parameter_space: ParameterSpace,
        recipe_id: str,
    ) -> None:
        self.run_root = Path(run_root)
        self.parameter_space = parameter_space
        self.recipe_id = recipe_id
        self._rows_by_slug = self._load_rows_by_slug()

    def _results_dir(self) -> Path:
        return self.run_root / "results"

    def write_csv(self, path: str | Path | None = None) -> Path:
        path = (
            Path(path) if path is not None else self._results_dir() / "q2d_raw_matrix_entries.csv"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=_sorted_fieldnames(self.matrix_table_rows))
            writer.writeheader()
            writer.writerows(self.matrix_table_rows)
        return path

    @property
    def matrix_table_rows(self) -> list[dict[str, Any]]:
        return [row for rows in self._rows_by_slug.values() for row in rows]

    def available_terminals(self) -> tuple[str, ...]:
        terminals = {
            row.get("row_terminal")
            for rows in self._rows_by_slug.values()
            for row in rows
            if row.get("row_terminal")
        }
        terminals.update(
            row.get("column_terminal")
            for rows in self._rows_by_slug.values()
            for row in rows
            if row.get("column_terminal")
        )
        return tuple(sorted(term for term in terminals if term))

    def available_matrix_elements(self) -> tuple[Q2dMatrixElement, ...]:
        elements = {
            Q2dMatrixElement(
                source=row.get("matrix_source"),
                quantity=row.get("quantity"),
                row=row.get("row_terminal"),
                column=row.get("column_terminal"),
            )
            for rows in self._rows_by_slug.values()
            for row in rows
            if row.get("matrix_source")
            and row.get("quantity")
            and row.get("row_terminal")
            and row.get("column_terminal")
        }
        return tuple(
            sorted(
                elements,
                key=lambda item: (item.source, item.quantity, item.row, item.column),
            )
        )

    def point(self, **fixed: Any) -> Q2dRawPoint:
        return self._as_raw_point(self.parameter_space.point(**fixed))

    def line(self, axis: str, **fixed: Any) -> list[Q2dRawPoint]:
        return [self._as_raw_point(point) for point in self.parameter_space.line(axis, **fixed)]

    def plane(self, a: str, b: str, **fixed: Any) -> list[Q2dRawPoint]:
        return [self._as_raw_point(point) for point in self.parameter_space.plane(a, b, **fixed)]

    def slice(self, vary: str | tuple[str, ...], **fixed: Any) -> list[Q2dRawPoint]:
        return [self._as_raw_point(point) for point in self.parameter_space.slice(vary, **fixed)]

    def derive(
        self,
        *formulas: Q2dFormula,
    ) -> Q2dDerivedSweepResult:
        if not formulas:
            raise ValueError("At least one formula is required")
        if len({formula.name for formula in formulas}) != len(formulas):
            raise ValueError("Formula names must be unique")
        rows = []
        for point in self.parameter_space.grid():
            raw_point = self._as_raw_point(point)
            row: dict[str, Any] = {
                "point_slug": raw_point.point_slug,
                "point_id": raw_point.point_id,
                **raw_point.coords,
            }
            for formula in formulas:
                row.update(formula.evaluate(raw_point))
            rows.append(row)
        return Q2dDerivedSweepResult(
            run_root=self.run_root,
            parameter_space=self.parameter_space,
            rows=rows,
            formulas=tuple(formulas),
        )

    def _as_raw_point(self, point: Any) -> Q2dRawPoint:
        point_slug = point.id.replace("=", "_")
        return Q2dRawPoint(
            point_id=point.id,
            point_slug=point_slug,
            coords=point.coords,
            matrix_rows=self._rows_by_slug[point_slug],
        )

    def _load_rows_by_slug(self) -> dict[str, list[dict[str, Any]]]:
        rows_by_slug: dict[str, list[dict[str, Any]]] = {}
        for point in self.parameter_space.grid():
            point_slug = str(point.id).replace("=", "_")
            result_dir = self.run_root / "points" / point_slug / self.recipe_id
            raw_point = load_q2d_raw_point_result(
                result_dir,
                point_id=point.id,
                point_slug=point_slug,
                coords=point.coords,
            )
            rows_by_slug[point_slug] = raw_point.matrix_table()
        return rows_by_slug


class Q2dDerivedSweepResult:
    """Derived Q2D metric rows backed by the same ``ParameterSpace``."""

    def __init__(
        self,
        *,
        run_root: str | Path,
        parameter_space: ParameterSpace,
        rows: list[dict[str, Any]],
        formulas: tuple[Q2dFormula, ...],
    ) -> None:
        self.run_root = Path(run_root)
        self.parameter_space = parameter_space
        self.rows = list(rows)
        self.formulas = formulas
        self._rows_by_slug = {row["point_slug"]: row for row in self.rows}

    def _results_dir(self) -> Path:
        return self.run_root / "results"

    def write_csv(self, path: str | Path | None = None) -> Path:
        path = Path(path or (self._results_dir() / "q2d_derived_metrics.csv"))
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=_sorted_fieldnames(self.rows))
            writer.writeheader()
            writer.writerows(self.rows)
        return path

    def write_formula_manifest(self, path: str | Path | None = None) -> Path:
        path = Path(path or (self._results_dir() / "q2d_derived_metrics.formulas.json"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "schema_version": "q2d-derived-metrics.formulas.v1",
                    "formulas": [formula.describe() for formula in self.formulas],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return path

    def point(self, **fixed: Any) -> Q2dResultView:
        point = self.parameter_space.point(**fixed)
        slug = point.id.replace("=", "_")
        fixed_coordinates = dict(point.coords)
        return self._view([self._rows_by_slug[slug]], axes=(), fixed=fixed_coordinates)

    def line(self, axis: str, **fixed: Any) -> Q2dResultView:
        rows = self._rows_for_points(self.parameter_space.line(axis, **fixed))
        return self._view(rows, axes=(axis,), fixed=self._fixed_coordinates((axis,), fixed))

    def plane(self, a: str, b: str, **fixed: Any) -> Q2dResultView:
        rows = self._rows_for_points(self.parameter_space.plane(a, b, **fixed))
        return self._view(rows, axes=(a, b), fixed=self._fixed_coordinates((a, b), fixed))

    def slice(self, vary: str | tuple[str, ...], **fixed: Any) -> Q2dResultView:
        points = self.parameter_space.slice(vary, **fixed)
        rows = self._rows_for_points(points)
        vary_axes = (vary,) if isinstance(vary, str) else tuple(vary)
        return self._view(rows, axes=vary_axes, fixed=self._fixed_coordinates(vary_axes, fixed))

    def _view(
        self,
        rows: list[dict[str, Any]],
        *,
        axes: tuple[str, ...],
        fixed: Mapping[str, Any],
    ) -> Q2dResultView:
        return Q2dResultView(
            rows,
            axes=axes,
            coordinate_columns=self.parameter_space.axis_names,
            fixed_coordinates=fixed,
            formulas=self.formulas,
            default_csv=self._default_view_csv(axes, fixed),
        )

    def _fixed_coordinates(
        self,
        axes: tuple[str, ...],
        fixed: Mapping[str, Any],
    ) -> dict[str, Any]:
        resolved = self.parameter_space.point(**fixed).coords
        return {key: value for key, value in resolved.items() if key not in axes}

    def _default_view_csv(self, axes: tuple[str, ...], fixed: Mapping[str, Any]) -> Path:
        axis_part = "point" if not axes else "_".join(axes)
        fixed_part = "__".join(
            f"{_file_slug(key)}_{_file_slug(value)}" for key, value in fixed.items()
        )
        suffix = "__".join(part for part in (axis_part, fixed_part) if part)
        return self._results_dir() / f"q2d_derived_view__{suffix}.csv"

    def _rows_for_points(self, points: Iterable[Any]) -> list[dict[str, Any]]:
        return [self._rows_by_slug[p.id.replace("=", "_")] for p in points]


def write_q2d_cross_section_payload(
    path: str | Path,
    cross_section: Q2dSemanticCrossSection,
) -> Path:
    """Write one semantic Q2D sidecar."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(cross_section.to_payload(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path


def _typed_payload(value: Any) -> dict[str, Any]:
    payload = asdict(value)
    if isinstance(value, Air):
        return {"kind": "air", **payload}
    if isinstance(value, DieGap):
        return {"kind": "die_gap", **payload}
    if isinstance(value, Die):
        return {"kind": "die", **payload}
    if isinstance(value, Ground):
        return {"kind": "ground", **payload}
    if isinstance(value, Gap):
        if value.role == "lateral_spacing":
            payload.pop("role")
        return {"kind": "gap", **payload}
    if isinstance(value, Trace):
        return {"kind": "trace", **payload}
    raise TypeError(f"Unsupported Q2D payload object: {type(value).__name__}")


def _require_name(label: str, value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} must not be empty")
    return text


def _require_positive(label: str, value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric, got {value!r}") from exc
    if number <= 0.0:
        raise ValueError(f"{label} must be positive, got {value!r}")
    return number


def _parse_q2d_matrix_csv(path: Path, *, point_slug: str) -> list[dict[str, Any]]:
    source = _matrix_source_from_path(path)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    setup, solution = _split_setup_solution(
        next((line.strip() for line in lines if line.strip()), "")
    )
    frequency, frequency_unit = _parse_number_unit(_header_value(lines, "Frequency"))
    units_by_quantity = _q2d_units_by_quantity(lines)
    rows = []
    index = 0
    while index < len(lines):
        quantity = _q2d_quantity_from_title(lines[index].strip())
        if quantity is None:
            index += 1
            continue
        header_index = index + 1
        while header_index < len(lines) and not lines[header_index].strip():
            header_index += 1
        columns = next(csv.reader([lines[header_index]]))[1:]
        row_index = header_index + 1
        while row_index < len(lines) and lines[row_index].strip():
            values = [part.strip() for part in next(csv.reader([lines[row_index]]))]
            rows.extend(
                {
                    "point_slug": point_slug,
                    "matrix_source": source,
                    "setup": setup,
                    "solution": solution,
                    "matrix_type": "Coupling Coefficient"
                    if "couple" in path.stem.lower()
                    else "Distributed Maxwell",
                    "quantity": quantity,
                    "row_terminal": values[0],
                    "column_terminal": column,
                    "value": _parse_float(raw_value),
                    "unit": "1"
                    if "couple" in path.stem.lower()
                    else units_by_quantity.get(quantity),
                    "frequency": frequency,
                    "frequency_unit": frequency_unit,
                    "source_file": str(path),
                }
                for column, raw_value in zip(columns, values[1:], strict=False)
                if column
            )
            row_index += 1
        index = row_index + 1
    return rows


def _matrix_source_from_path(path: Path) -> Q2dMatrixSource:
    stem = path.stem.lower()
    if stem == "cg_maxwell_matrix":
        return "cg_maxwell"
    if stem == "rl_maxwell_matrix":
        return "rl_maxwell"
    if stem == "cg_couple_matrix":
        return "cg_couple"
    if stem == "rl_couple_matrix":
        return "rl_couple"
    raise ValueError(f"Unsupported Q2D matrix file: {path}")


def _split_setup_solution(text: str) -> tuple[str | None, str | None]:
    if ":" not in text:
        return text or None, None
    setup, solution = text.split(":", 1)
    return setup.strip() or None, solution.strip() or None


def _header_value(lines: list[str], key: str) -> str | None:
    prefix = key + ":"
    return next(
        (line.split(":", 1)[1].strip() for line in lines if line.strip().startswith(prefix)), None
    )


def _parse_number_unit(text: str | None) -> tuple[float | None, str | None]:
    if not text:
        return None, None
    match = re.fullmatch(r"([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?)\s*([A-Za-z/]+)", text)
    return (float(match.group(1)), match.group(2)) if match else (None, text)


def _parse_float(text: str) -> float | None:
    try:
        return float(text)
    except ValueError:
        return None


def _q2d_units_by_quantity(lines: list[str]) -> dict[str, str]:
    units = {}
    for line in lines:
        for part in line.split(","):
            if "Units:" in part:
                key, unit = part.split("Units:", 1)
                if key.strip() in {"C", "G", "L", "R"}:
                    units[key.strip()] = unit.strip()
    return units


def _q2d_quantity_from_title(title: str) -> str | None:
    return {
        "Capacitance Matrix": "C",
        "Conductance Matrix": "G",
        "Inductance Matrix": "L",
        "Resistance Matrix": "R",
    }.get(title.replace(" Coupling Coefficient", "").strip())


def _si_per_meter(value: Any, unit: Any, quantity: str) -> float:
    if value is None:
        raise ValueError(f"Q2D {quantity} matrix entry has no numeric value")
    value = float(value)
    unit = {"F/m": "F/meter", "H/m": "H/meter"}.get(
        str(unit or "").strip(), str(unit or "").strip()
    )
    scale = {"f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3, "": 1.0}
    if quantity == "C" and unit == "farad/meter":
        return value
    if quantity == "L" and unit == "H/meter":
        return value
    match = re.fullmatch(r"([fpnum]?)([FH])/meter", unit)
    if match and ((quantity, match.group(2)) in {("C", "F"), ("L", "H")}):
        return value * scale[match.group(1)]
    raise ValueError(f"Unsupported Q2D {quantity} unit: {unit!r}")


__all__ = [
    "Air",
    "Die",
    "DieGap",
    "FacePattern",
    "Gap",
    "GapRole",
    "Ground",
    "Q2dDerivedSweepResult",
    "Q2dFacetLineGrid",
    "Q2dFormula",
    "Q2dHeatMap",
    "Q2dImpedanceFormula",
    "Q2dLinePlot",
    "Q2dMatrixElement",
    "Q2dRawPoint",
    "Q2dRawSweepResult",
    "Q2dResultView",
    "load_q2d_raw_sweep_result",
    "load_q2d_raw_point_result",
    "make_q2d_same_face_single_trace_cross_section",
    "make_q2d_same_face_two_trace_cross_section",
    "Q2dSemanticCrossSection",
    "Stack",
    "Trace",
    "validate_q2d_cross_section_payload",
    "validate_q2d_single_reference_upper_ground_clearance_payload",
    "validate_q2d_same_face_upper_ground_clearance_payload",
    "write_q2d_cross_section_payload",
]
