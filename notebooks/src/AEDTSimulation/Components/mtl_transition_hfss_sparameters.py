# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.3
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
# # MTL transition HFSS wave-port S-parameters
#
# This notebook builds one transition coupon directly from public transition cells and
# assigns physical wave ports on external faces only. `RUN_PREPARE` and
# `RUN_SOLVER` are `False` by default for safe GUI review.

# %% [markdown]
# ## Controls

# %%
from __future__ import annotations

import json
from dataclasses import dataclass
from math import cos, pi, sin
from pathlib import Path
from time import perf_counter, sleep
from typing import Any

import gdsfactory as gf
import pandas as pd
import skrf
from ansys.aedt.core import Hfss
from gdsfactory import kdb
from IPython.display import HTML, clear_output, display

import orpen_sc_pdk
from orpen_sc_pdk.cells.cpw import mtl_bend_bend_transition, mtl_straight_bend_transition
from orpen_sc_pdk.simulation.aedt import aedt_material_name_from_physical_key
from orpen_sc_pdk.tech import (
    CPW_DRAW,
    CPW_GROUND_MASK,
    OUTER_VACUUM_THICKNESS_UM,
    SUBSTRATE_THICKNESS_UM,
)

REPO_ROOT = Path(orpen_sc_pdk.__file__).resolve().parent.parent
if not (REPO_ROOT / "orpen_sc_pdk").is_dir():
    raise RuntimeError("Active orpen_sc_pdk checkout is invalid for notebook replay.")
orpen_sc_pdk.activate()

TRANSITION_KIND = "straight_bend"  # {"straight_bend", "bend_bend"}
LEAD_LENGTH_UM = 50.0
GUARD_LENGTH_UM = 50.0
DEEMBED_LENGTH_UM = 0.0
SUBSTRATE_KEY = "Si"

# Lead lengths currently swept in formal studies; this notebook is single-point review only.
SWEEP_LENGTH_UM_OPTIONS = (50, 60, 80, 100, 200)

FREQUENCY_START_GHZ = 3.0
FREQUENCY_STOP_GHZ = 8.0
FREQUENCY_POINT_COUNT = 20_000
SWEEP_TYPE = "Fast"
SWEEP_NAME = "S"

MAX_ADAPTIVE_PASSES = 99
MINIMUM_CONVERGED_PASSES = 2
MAX_DELTA_S = 0.02

SOLVER_SETUP_NAME = "Setup1"
SOLUTION_TYPE = "Terminal"
NON_GRAPHICAL = True
CLOSE_DESKTOP = False

# Execution controls are intentionally off in committed notebook.
RUN_PREPARE = False
RUN_SOLVER = False
RUN_AEDT = RUN_PREPARE or RUN_SOLVER

RUN_DIR = (
    REPO_ROOT
    / "build"
    / "simulation"
    / "aedt"
    / "mtl_transition_hfss_sparameters"
    / TRANSITION_KIND
    / f"lead_{LEAD_LENGTH_UM:g}um_deembed_{DEEMBED_LENGTH_UM:g}um"
)
GDS_PATH = RUN_DIR / f"mtl_transition_{TRANSITION_KIND}.gds"
PROJECT_PATH = RUN_DIR / f"mtl_transition_{TRANSITION_KIND}.aedt"
TOUCHSTONE_PATH = RUN_DIR / "mtl_transition.s4p"
TIMING_PATH = RUN_DIR / "solve_timing.json"
S_PARAMETER_PLOT_PATH = RUN_DIR / "sparameters.html"
METADATA_PATH = RUN_DIR / "mtl_transition_metadata.json"
ACF_PATH = REPO_ROOT / "notebooks" / "AEDTSimulation" / "HFSS_Local.acf"

# HFSS-only GDS layers used only for this coupon.
HFSS_SIGNAL_P_LAYER = (905, 0)
HFSS_SIGNAL_R_LAYER = (906, 0)
HFSS_GROUND_LAYER = (907, 0)
HFSS_SUBSTRATE_LAYER = (908, 0)

# Region padding order is [+X, -X, +Y, -Y, +Z, -Z].
REGION_PAD = OUTER_VACUUM_THICKNESS_UM

# Terminal names as emitted by PyAEDT's created boundary objects.
CANONICAL_TERMINAL_ORDER = ("o1", "o2", "o3", "o4")


class BuildError(RuntimeError):
    """Raised when geometry, port mapping, or boundary creation is not exact."""


@dataclass(frozen=True)
class PortRecord:
    physical_port: str
    object_name: str
    side: str
    axis: str
    side_sign: int
    port_center_um: tuple[float, float, float]


@dataclass(frozen=True)
class TerminalRecord:
    physical_port: str
    boundary_name: str
    terminal_names: list[str]
    terminal_objects: dict[str, str]
    face_id: int
    expected_terminal_count: int


def _normalize_transition_kind(kind: str) -> str:
    normalized = str(kind).strip().lower().replace("-", "_").replace(" ", "_")
    if normalized not in {"straight_bend", "bend_bend"}:
        raise ValueError(f"Unsupported TRANSITION_KIND: {kind!r}.")
    return normalized


def _deembed_mm(deembed_length_um: float) -> float:
    if deembed_length_um < 0:
        raise ValueError(f"DEEMBED_LENGTH_UM must be >= 0, got {deembed_length_um!r}.")
    return deembed_length_um / 1000.0


def _deembed_um(deembed_length_um: float) -> str:
    if deembed_length_um < 0:
        raise ValueError(f"DEEMBED_LENGTH_UM must be >= 0, got {deembed_length_um!r}.")
    return f"{deembed_length_um:g}um"


def _deembed_example_mm() -> float:
    return max(0.0, LEAD_LENGTH_UM - GUARD_LENGTH_UM) / 1000.0


def _normalization_index(
    source_port_names: list[str], canonical_order: tuple[str, ...]
) -> tuple[list[int], list[str], list[str]]:
    if len(source_port_names) != len(canonical_order):
        raise BuildError(
            f"Touchstone port count mismatch: expected {len(canonical_order)} ports, "
            f"got {len(source_port_names)}."
        )

    if len(set(source_port_names)) != len(source_port_names):
        raise BuildError(f"Touchstone export contains duplicate port names: {source_port_names!r}.")

    canonical = list(canonical_order)
    missing = [name for name in canonical if name not in source_port_names]
    extra = [name for name in source_port_names if name not in canonical]
    if missing or extra:
        raise BuildError(
            "Touchstone port names are not a permutation of canonical order. "
            f"expected={canonical!r}, got={source_port_names!r}, "
            f"missing={missing!r}, extra={extra!r}."
        )

    index = [source_port_names.index(name) for name in canonical]
    return index, source_port_names, canonical


def _normalize_touchstone_ports(
    touchstone_path: Path,
    canonical_port_order: tuple[str, ...],
    *,
    form: str = "ma",
    r_ref: float = 50.0,
) -> dict[str, list[str] | bool]:
    network = skrf.Network(str(touchstone_path))
    if not network.port_names:
        raise BuildError(f"Touchstone export at {touchstone_path!s} has no readable port names.")

    index, original_order, normalized_order = _normalization_index(
        list(network.port_names),
        canonical_port_order,
    )

    if list(network.port_names) != normalized_order:
        network.s = network.s[:, index, :][:, :, index]
        network.z0 = network.z0[:, index]
        network.port_names = normalized_order
        network.write_touchstone(
            str(touchstone_path),
            form=form,
            r_ref=r_ref,
            write_z0=False,
            skrf_comment=True,
        )
    return {
        "original_port_order": original_order,
        "normalized_port_order": normalized_order,
        "was_reordered": original_order != normalized_order,
    }


def _side_map(kind: str) -> dict[str, str]:
    if kind == "straight_bend":
        # seam at -X, outer1 at +Y, outer2 at +X
        return {
            "o1": "-X",
            "o2": "-X",
            "o3": "+Y",
            "o4": "+X",
        }
    if kind == "bend_bend":
        # seam at -X, outer1 at +Y, outer2 at -Y
        return {
            "o1": "-X",
            "o2": "-X",
            "o3": "+Y",
            "o4": "-Y",
        }
    raise BuildError(f"Unknown transition kind {kind!r}.")


def _object_map() -> dict[str, str]:
    return {
        "o1": "signal_1",
        "o2": "signal_2",
        "o3": "signal_2",
        "o4": "signal_1",
    }


def _build_transition_component(kind: str) -> tuple[gf.Component, list[str]]:
    if kind == "straight_bend":
        component = mtl_straight_bend_transition(
            straight_length=100.0,
            inter_trace_ground_width=3.0,
            bend_radius=100.0,
            lead_length=LEAD_LENGTH_UM,
        )
    elif kind == "bend_bend":
        component = mtl_bend_bend_transition(
            bend_radius=100.0,
            inter_trace_ground_width=3.0,
            lead_length=LEAD_LENGTH_UM,
        )
    else:
        raise ValueError(f"Unsupported transition kind {kind!r}.")

    expected_ports = {"o1", "o2", "o3", "o4"}
    observed_ports = {port.name for port in component.ports}
    if observed_ports != expected_ports:
        raise BuildError(
            "Transition component ports mismatch. "
            f"Expected {sorted(expected_ports)}, got {sorted(observed_ports)}."
        )
    ordered = list(component.info.get("ordered_port_names", ()))
    if ordered != ["o1", "o2", "o3", "o4"]:
        raise BuildError(
            "Transition component port ordering changed from accepted contract: "
            f"expected ['o1','o2','o3','o4'], got {ordered!r}."
        )
    return component, ordered


def _signal_polygon_at_port(
    signal_region: kdb.Region, *, port: gf.Port, dbu_um: float
) -> kdb.Polygon:
    if port.orientation is None:
        raise BuildError(f"Port {port.name!r} must expose orientation.")
    probe_distance_um = max(dbu_um, float(port.width) / 4)
    angle = float(port.orientation) * pi / 180
    probe = kdb.Point(
        round((float(port.x) - probe_distance_um * cos(angle)) / dbu_um),
        round((float(port.y) - probe_distance_um * sin(angle)) / dbu_um),
    )
    matches = [polygon for polygon in signal_region.each() if polygon.inside(probe)]
    if len(matches) != 1:
        raise BuildError(
            f"Port {port.name!r} must match exactly one signal polygon, got {len(matches)}."
        )
    return matches[0]


def _select_region_layer_ports(
    component: gf.Component,
) -> tuple[kdb.Region, kdb.Region]:
    xs = gf.get_cross_section("cpw_6_7_6")
    draw_layer = tuple(int(value) for value in gf.get_layer_tuple(xs[CPW_DRAW].layer))
    gm_layer = tuple(int(value) for value in gf.get_layer_tuple(xs[CPW_GROUND_MASK].layer))

    signal_region = component.get_region(draw_layer, merge=True)
    ground_mask_region = component.get_region(gm_layer, merge=True)
    if signal_region.count() == 0:
        raise BuildError("Transition has no signal region on CPW draw layer.")
    if ground_mask_region.count() == 0:
        raise BuildError("Transition has no ground-mask region on CPW ground mask layer.")
    return signal_region, ground_mask_region


def _build_hfss_coupon_from_transition(
    component: gf.Component,
    *,
    transition_kind: str,
) -> tuple[gf.Component, list[PortRecord]]:
    signal_region, ground_mask_region = _select_region_layer_ports(component)

    signal_polygons = {
        "signal_1": _signal_polygon_at_port(
            signal_region, port=component.ports["o1"], dbu_um=component.kcl.dbu
        ),
        "signal_2": _signal_polygon_at_port(
            signal_region, port=component.ports["o2"], dbu_um=component.kcl.dbu
        ),
    }
    if signal_polygons["signal_1"] == signal_polygons["signal_2"]:
        raise BuildError("Coupled traces collapsed; expected separate seam traces.")

    trace_bbox = signal_region.bbox()
    mask_bbox = ground_mask_region.bbox()
    left = min(trace_bbox.left, mask_bbox.left)
    bottom = min(trace_bbox.bottom, mask_bbox.bottom)
    right = max(trace_bbox.right, mask_bbox.right)
    top = max(trace_bbox.top, mask_bbox.top)
    coupon_box = kdb.Box(
        left,
        bottom,
        right,
        top,
    )

    ground_region = kdb.Region(coupon_box) - ground_mask_region
    if ground_region.is_empty():
        raise BuildError("Finite ground region is empty; geometry subtraction failed.")

    hfss_coupon = gf.Component()
    hfss_coupon.add_polygon(kdb.Region(signal_polygons["signal_1"]), layer=HFSS_SIGNAL_P_LAYER)
    hfss_coupon.add_polygon(kdb.Region(signal_polygons["signal_2"]), layer=HFSS_SIGNAL_R_LAYER)
    hfss_coupon.add_polygon(ground_region, layer=HFSS_GROUND_LAYER)
    hfss_coupon.add_polygon(kdb.Region(coupon_box), layer=HFSS_SUBSTRATE_LAYER)

    hfss_coupon.add_port(
        name="o1",
        port=component.ports["o1"],
        layer=HFSS_SIGNAL_P_LAYER,
    )
    hfss_coupon.add_port(
        name="o2",
        port=component.ports["o2"],
        layer=HFSS_SIGNAL_R_LAYER,
    )
    hfss_coupon.add_port(
        name="o3",
        port=component.ports["o3"],
        layer=HFSS_SIGNAL_P_LAYER,
    )
    hfss_coupon.add_port(
        name="o4",
        port=component.ports["o4"],
        layer=HFSS_SIGNAL_R_LAYER,
    )
    hfss_coupon.flatten(merge=True)

    side_map = _side_map(transition_kind)
    hfss_coupon.info["hfss_coupon"] = {
        "transition_kind": transition_kind,
        "lead_length_um": float(LEAD_LENGTH_UM),
        "guard_length_um": float(GUARD_LENGTH_UM),
        "deembed_length_um": float(DEEMBED_LENGTH_UM),
        "hfss_layers": {
            "signal_1": HFSS_SIGNAL_P_LAYER,
            "signal_2": HFSS_SIGNAL_R_LAYER,
            "finite_ground": HFSS_GROUND_LAYER,
            "substrate": HFSS_SUBSTRATE_LAYER,
        },
        "materials": {
            "signal_1": "PEC",
            "signal_2": "PEC",
            "finite_ground": "PEC",
            "substrate": "Si",
        },
        "bbox_um": {
            "xmin": coupon_box.left * component.kcl.dbu,
            "xmax": coupon_box.right * component.kcl.dbu,
            "ymin": coupon_box.bottom * component.kcl.dbu,
            "ymax": coupon_box.top * component.kcl.dbu,
        },
    }

    port_records = [
        PortRecord(
            physical_port=name,
            object_name=_object_map()[name],
            side=side,
            axis=side[1],
            side_sign=-1 if side[0] == "-" else 1,
            port_center_um=tuple(float(v) for v in component.ports[name].center),
        )
        for name, side in side_map.items()
    ]
    return hfss_coupon, port_records


def _region_padding_for_kind(kind: str) -> list[float]:
    # PyAEDT assigns the Wave Port to the whole selected Region face, so XY padding would grow
    # the face aperture. Keep XY pads zero so both kinds share equal external cross-sections;
    # keep only Z padding explicit for vertical clearance.
    if kind not in {"straight_bend", "bend_bend"}:
        raise BuildError(f"Unsupported transition kind {kind!r}.")
    return [0.0, 0.0, 0.0, 0.0, REGION_PAD, REGION_PAD]


def _find_region_face_on_side(app: Hfss, side: str) -> int:
    obj = app.modeler.get_object_from_name("Region")
    faces = list(obj.faces)
    if not faces:
        raise BuildError("No faces found on imported 'Region'.")
    axis = 0 if side[1] == "X" else 1
    sign = -1 if side[0] == "-" else 1

    def score(face: Any) -> tuple[float, float]:
        center = getattr(face, "center", None)
        if not center:
            raise BuildError("Face on 'Region' has no center metadata.")
        axis_value = float(center[axis])
        return sign * axis_value, float(center[2])

    chosen = max(faces, key=score)
    return int(chosen.id)


def _create_wave_port(
    app: Hfss,
    *,
    ground_references: list[str],
    terminal_names: list[str],
    terminal_object_map: dict[str, str],
    physical_port: str,
    face_id: int,
    boundary_name: str,
    deembed_distance: float | str,
    prior_terminals: set[str],
) -> TerminalRecord:
    boundary = app.wave_port(
        face_id,
        reference=ground_references,
        name=boundary_name,
        deembed=deembed_distance,
        terminals_rename=True,
    )
    if not boundary:
        raise BuildError(f"PyAEDT wave_port() returned None for {boundary_name!r}.")

    post = list(app.oboundary.GetExcitationsOfType("Terminal"))
    new_terms = [term for term in post if term not in prior_terminals]
    expected_terminal_count = len(terminal_names)
    if len(new_terms) != expected_terminal_count:
        raise BuildError(
            f"Physical port {physical_port!r} expected {expected_terminal_count} terminal(s), "
            f"created {len(new_terms)}."
        )

    for generated_name, semantic_name in zip(new_terms, terminal_names, strict=True):
        app.oboundary.RenameBoundary(generated_name, semantic_name)

    return TerminalRecord(
        physical_port=physical_port,
        boundary_name=boundary_name,
        terminal_names=terminal_names,
        terminal_objects=terminal_object_map,
        face_id=face_id,
        expected_terminal_count=expected_terminal_count,
    )


def _assign_ports(
    app: Hfss,
    transition_kind: str,
    assignments: list[PortRecord],
    ground_references: list[str],
    deembed_distance: float | str,
) -> list[TerminalRecord]:
    expected = _side_map(transition_kind)
    region_faces = {
        name: _find_region_face_on_side(app, expected[name])
        for name in expected
    }

    outer_records = [r for r in assignments if r.physical_port in {"o3", "o4"}]

    prior = set(app.oboundary.GetExcitationsOfType("Terminal"))
    terminal_records: list[TerminalRecord] = []

    seam_region_face = region_faces["o1"]
    terminal_records.append(
        _create_wave_port(
            app,
            ground_references=ground_references,
            terminal_names=CANONICAL_TERMINAL_ORDER[:2],
            terminal_object_map={"o1": _object_map()["o1"], "o2": _object_map()["o2"]},
            physical_port="seam",
            face_id=seam_region_face,
            boundary_name="seam",
            deembed_distance=deembed_distance,
            prior_terminals=prior,
        )
    )

    for rec in outer_records:
        face_id = region_faces[rec.physical_port]
        prior = set(app.oboundary.GetExcitationsOfType("Terminal"))
        terminal_records.append(
            _create_wave_port(
                app,
                ground_references=ground_references,
                physical_port=rec.physical_port,
                face_id=face_id,
                terminal_names=[rec.physical_port],
                terminal_object_map={rec.physical_port: _object_map()[rec.physical_port]},
                boundary_name=f"{rec.physical_port}_wave_port",
                deembed_distance=deembed_distance,
                prior_terminals=prior,
            )
        )

    all_terminals = list(app.oboundary.GetExcitationsOfType("Terminal"))
    if len(all_terminals) != 4:
        raise BuildError(
            f"Expected 4 terminal excitations after assignment, got {len(all_terminals)}."
        )

    return terminal_records


# %% [markdown]
# ## Review table and de-embed examples

# %%
TRANSITION_KIND = _normalize_transition_kind(TRANSITION_KIND)
DEEMBED_MM_EXPLICIT = _deembed_mm(DEEMBED_LENGTH_UM)
DEEMBED_UM_EXPLICIT = _deembed_um(DEEMBED_LENGTH_UM)
DEEMBED_MM_FROM_GUARD = _deembed_example_mm()

print(f"Transition kind: {TRANSITION_KIND}")
print(f"DEEMBED (explicit UI value): {DEEMBED_MM_EXPLICIT:.6f} mm")
print(f"DEEMBED for PyAEDT wave_port: {DEEMBED_UM_EXPLICIT}")
print(
    f"Guard-convention example: max(0, {LEAD_LENGTH_UM} - {GUARD_LENGTH_UM})/1000 = "
    f"{DEEMBED_MM_FROM_GUARD:.6f} mm"
)
print(
    "Do not copy the guard formula into defaults: set DEEMBED_LENGTH_UM explicitly when "
    "sweeping. Current commit keeps review default DEEMBED_LENGTH_UM=0.0."
)
print(f"Reference lead sweep options: {SWEEP_LENGTH_UM_OPTIONS}")


# %% [markdown]
# ## Build Transition Coupon

# %%
transition, ordered_ports = _build_transition_component(TRANSITION_KIND)
coupon, port_records = _build_hfss_coupon_from_transition(
    transition,
    transition_kind=TRANSITION_KIND,
)

if coupon.info["hfss_coupon"]["transition_kind"] != TRANSITION_KIND:
    raise BuildError("Coupon metadata transition kind mismatch.")

display(coupon.plot())

df_ports = pd.DataFrame(
    [
        {
            "port": rec.physical_port,
            "object": rec.object_name,
            "side": rec.side,
            "axis": rec.axis,
            "side_sign": rec.side_sign,
            "port_center_um": rec.port_center_um,
        }
        for rec in port_records
    ]
)

display(df_ports)

print(f"Public ordered ports from cell: {ordered_ports}")


# %% [markdown]
# ## Initialize HFSS App

# %%
if RUN_AEDT:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    hfss = Hfss(
        project=str(PROJECT_PATH),
        design=f"mtl_transition_{TRANSITION_KIND}",
        solution_type=SOLUTION_TYPE,
        non_graphical=NON_GRAPHICAL,
        new_desktop=True,
        close_on_exit=False,
    )
    hfss.modeler.model_units = "um"
    hfss.modeler.refresh_all_ids()
    build_model = bool(not hfss.modeler.object_names)
    print("Resuming existing project." if not build_model else "Created new HFSS project.")
else:
    hfss = None
    build_model = False
    print("AEDT is not started. Set RUN_PREPARE or RUN_SOLVER to initialize HFSS app.")


# %% [markdown]
# ## Import geometry, region, and assign wave ports

# %%
if RUN_AEDT and build_model:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    coupon.write_gds(GDS_PATH, with_metadata=False)

    layer_mapping = {
        HFSS_SIGNAL_P_LAYER[0]: (0.0, 0.0),
        HFSS_SIGNAL_R_LAYER[0]: (0.0, 0.0),
        HFSS_GROUND_LAYER[0]: (0.0, 0.0),
        HFSS_SUBSTRATE_LAYER[0]: (-SUBSTRATE_THICKNESS_UM, SUBSTRATE_THICKNESS_UM),
    }
    if not hfss.import_gds_3d(str(GDS_PATH), layer_mapping, units="um", import_method=1):
        raise BuildError(f"Could not import GDS: {GDS_PATH}")
    hfss.modeler.refresh_all_ids()

    expected = (
        (HFSS_SIGNAL_P_LAYER[0], "signal_1"),
        (HFSS_SIGNAL_R_LAYER[0], "signal_2"),
        (HFSS_GROUND_LAYER[0], "finite_ground"),
        (HFSS_SUBSTRATE_LAYER[0], "substrate"),
    )
    substrate_material_name = aedt_material_name_from_physical_key(SUBSTRATE_KEY)
    imported = {}
    ground_references = []
    for layer_number, expected_name in expected:
        matches = [
            name
            for name in hfss.modeler.object_names
            if name.startswith(f"signal{layer_number}_")
        ]
        if not matches:
            raise BuildError(f"Missing imported object for {expected_name!r}.")
        if expected_name == "finite_ground":
            ground_references = []
            for index, selected in enumerate(matches, start=1):
                imported_obj = hfss.modeler.get_object_from_name(selected)
                imported_obj.name = f"finite_ground_{index}"
                ground_references.append(imported_obj.name)
            imported[expected_name] = ground_references
            continue
        if len(matches) != 1:
            raise BuildError(
                f"Expected one imported object for {expected_name!r}, got {matches!r}."
            )
        selected = matches[0]
        imported_obj = hfss.modeler.get_object_from_name(selected)
        imported_obj.name = expected_name
        if expected_name == "substrate":
            imported_obj.material_name = substrate_material_name
        imported[expected_name] = imported_obj.name

    hfss.modeler.refresh_all_ids()

    region = hfss.modeler.create_region(
        pad_value=_region_padding_for_kind(TRANSITION_KIND),
        pad_type="Absolute Offset",
        name="Region",
    )
    region.material_name = "vacuum"
    hfss.assign_perfect_e(["signal_1", "signal_2", *ground_references], name="PerfectE")

    terminal_records = _assign_ports(
        hfss,
        transition_kind=TRANSITION_KIND,
        assignments=port_records,
        ground_references=ground_references,
        deembed_distance=DEEMBED_UM_EXPLICIT,
    )

    all_terminals = list(hfss.oboundary.GetExcitationsOfType("Terminal"))
    if len(all_terminals) != 4:
        raise BuildError(
            f"Terminal inventory failed: expected 4, got {len(all_terminals)} -> {all_terminals!r}."
        )

    metadata = {
        "transition_kind": TRANSITION_KIND,
        "lead_length_um": float(LEAD_LENGTH_UM),
        "guard_length_um": float(GUARD_LENGTH_UM),
        "deembed_length_um": float(DEEMBED_LENGTH_UM),
        "deembed_um_explicit": DEEMBED_UM_EXPLICIT,
        "deembed_mm_explicit": DEEMBED_MM_EXPLICIT,
        "deembed_mm_from_guard": DEEMBED_MM_FROM_GUARD,
        "explicit_deembed_note": (
            "Guard formula is an example only. In this notebook DEEMBED_LENGTH_UM is used directly "
            "and remains the source-of-truth parameter."
        ),
        "frequency_ghz": [FREQUENCY_START_GHZ, FREQUENCY_STOP_GHZ, FREQUENCY_POINT_COUNT],
        "frequency_sweep_type": SWEEP_TYPE,
        "sweep_name": SWEEP_NAME,
        "expected_terminal_order": CANONICAL_TERMINAL_ORDER,
        "physical_port_faces": {
            rec.physical_port: {
                "side": (
                    _side_map(TRANSITION_KIND)["o1"]
                    if rec.physical_port == "seam"
                    else _side_map(TRANSITION_KIND)[rec.physical_port]
                ),
                "face_id": rec.face_id,
                "expected_terminal_count": rec.expected_terminal_count,
            }
            for rec in terminal_records
        },
        "physical_port_faces_with_actual_order": [
            {
                "physical_port": rec.physical_port,
                "boundary_name": rec.boundary_name,
                "face_id": rec.face_id,
                "expected_terminal_count": rec.expected_terminal_count,
                "terminal_names": rec.terminal_names,
                "terminal_objects": rec.terminal_objects,
            }
            for rec in terminal_records
        ],
        "seam_subports": ["o1", "o2"],
        "region_padding_um": _region_padding_for_kind(TRANSITION_KIND),
        "solver_setup": {
            "name": SOLVER_SETUP_NAME,
            "solution_type": SOLUTION_TYPE,
            "max_adaptive_passes": MAX_ADAPTIVE_PASSES,
            "minimum_converged_passes": MINIMUM_CONVERGED_PASSES,
            "max_delta_s": MAX_DELTA_S,
        },
    }

    RUN_DIR.mkdir(parents=True, exist_ok=True)
    METADATA_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Saved review metadata: {METADATA_PATH}")


# %% [markdown]
# ## Geometry and metadata validation

# %%
if RUN_AEDT and build_model:
    if not METADATA_PATH.exists():
        raise BuildError("Expected metadata file was not emitted.")

    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    excitations = hfss.oboundary.GetExcitationsOfType("Terminal")
    if len(excitations) != 4:
        raise BuildError(f"Terminal validation failed, got {excitations!r}.")

    if metadata.get("expected_terminal_order") != list(CANONICAL_TERMINAL_ORDER):
        raise BuildError("expected_terminal_order metadata mismatch.")

    expected_face_sides = _side_map(TRANSITION_KIND)
    for rec in port_records:
        side = expected_face_sides[rec.physical_port]
        if rec.side != side:
            raise BuildError(f"Port {rec.physical_port!r} side mismatch: {rec.side!r} vs {side!r}.")

    print("Geometry and metadata validation passed.")


# %% [markdown]
# ## Setup

# %%
if RUN_AEDT and build_model:
    setup = (
        hfss.get_setup(SOLVER_SETUP_NAME)
        if SOLVER_SETUP_NAME in hfss.setup_names
        else hfss.create_setup(SOLVER_SETUP_NAME)
    )
    if not setup.enable_adaptive_setup_broadband(
        f"{FREQUENCY_START_GHZ}GHz",
        f"{FREQUENCY_STOP_GHZ}GHz",
        max_passes=MAX_ADAPTIVE_PASSES,
        max_delta_s=MAX_DELTA_S,
    ):
        raise BuildError("HFSS broadband setup failed.")

    # This extraction needs terminal S only. Saving every field made earlier
    # coupons unnecessarily large; turn fields on only for a dedicated field run.
    setup.props["SaveAnyFields"] = False
    setup.props["SaveRadFieldsOnly"] = False
    setup.props["MinimumConvergedPasses"] = MINIMUM_CONVERGED_PASSES
    if not setup.update():
        raise BuildError("Failed to write min converged pass count.")

    sweep = setup.get_sweep(SWEEP_NAME)
    if sweep:
        sweep.props.update(
            {
                "RangeType": "LinearCount",
                "RangeStart": f"{FREQUENCY_START_GHZ}GHz",
                "RangeEnd": f"{FREQUENCY_STOP_GHZ}GHz",
                "RangeCount": FREQUENCY_POINT_COUNT,
                "Type": SWEEP_TYPE,
                "SaveFields": False,
                "SaveRadFields": False,
            }
        )
        sweep.update()
    else:
        sweep = hfss.create_linear_count_sweep(
            SOLVER_SETUP_NAME,
            "GHz",
            FREQUENCY_START_GHZ,
            FREQUENCY_STOP_GHZ,
            num_of_freq_points=FREQUENCY_POINT_COUNT,
            name=SWEEP_NAME,
            save_fields=False,
            sweep_type=SWEEP_TYPE,
        )
        if not sweep:
            raise BuildError(f"Failed to create {SWEEP_TYPE} frequency sweep.")

    hfss.save_project()


# %% [markdown]
# ## Simulation and outputs

# %%
if RUN_SOLVER and RUN_AEDT:
    setup = hfss.get_setup(SOLVER_SETUP_NAME)
    started = perf_counter()
    solved = hfss.analyze_setup(
        SOLVER_SETUP_NAME,
        acf_file=str(ACF_PATH),
        revert_to_initial_mesh=False,
        blocking=False,
    )
    if not solved:
        raise BuildError(f"HFSS setup {SOLVER_SETUP_NAME} did not start.")

    # A blocking Analyze call makes a Human-run notebook look frozen. Poll the
    # same adaptive-pass profile shown in AEDT while the native solve continues.
    sleep(1)
    completed_passes = 0
    while hfss.are_there_simulations_running:
        profiles = setup.get_profile()
        completed_passes = (
            max((profile.num_adaptive_passes for profile in profiles.values()), default=0)
            if profiles
            else completed_passes
        )
        clear_output(wait=True)
        display(
            HTML(
                f"<b>HFSS is running</b> &middot; "
                f"{completed_passes} adaptive passes completed &middot; "
                f"{perf_counter() - started:.1f} s elapsed"
            )
        )
        sleep(5)

    completed_passes = max(
        (profile.num_adaptive_passes for profile in setup.get_profile().values()),
        default=completed_passes,
    )
    solve_seconds = perf_counter() - started
    clear_output(wait=True)
    display(
        HTML(
            f"<b>HFSS solve complete</b> &middot; "
            f"{completed_passes} adaptive passes &middot; {solve_seconds:.1f} s"
        )
    )
    timing = {
        "analyze_setup_seconds": solve_seconds,
        "completed_adaptive_passes": completed_passes,
        "transition_kind": TRANSITION_KIND,
        "lead_length_um": LEAD_LENGTH_UM,
        "deembed_length_um": DEEMBED_LENGTH_UM,
        "guard_length_um": GUARD_LENGTH_UM,
    }

    touchstone = hfss.export_touchstone(
        setup=SOLVER_SETUP_NAME,
        sweep=SWEEP_NAME,
        output_file=str(TOUCHSTONE_PATH),
    )
    if not touchstone:
        raise BuildError(f"Touchstone export failed for {TOUCHSTONE_PATH}")

    touchstone_normalization = _normalize_touchstone_ports(
        TOUCHSTONE_PATH,
        CANONICAL_TERMINAL_ORDER,
        form="ma",
        r_ref=50.0,
    )
    if METADATA_PATH.exists():
        metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
        metadata["touchstone_path"] = str(TOUCHSTONE_PATH)
        metadata["touchstone_normalization"] = touchstone_normalization
        metadata["touchstone_form"] = "ma"
        metadata["touchstone_reference_ohm"] = 50.0
        METADATA_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    timing["touchstone_path"] = str(TOUCHSTONE_PATH)
    timing.update(
        {f"touchstone_{name}": value for name, value in touchstone_normalization.items()},
    )
    TIMING_PATH.write_text(json.dumps(timing, indent=2), encoding="utf-8")

    print(f"Touchstone written to: {touchstone}")
    print(f"Timing written to: {TIMING_PATH}")
elif not RUN_SOLVER:
    print("No solve requested; set RUN_SOLVER=True when solver execution is desired.")


# %% [markdown]
# ## Physics Analysis Output Table

# %%
if METADATA_PATH.exists():
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    preview_records = []
    for item in metadata.get("physical_port_faces_with_actual_order", []):
        preview_records.append(
            {
                "physical_port": item.get("physical_port"),
                "face_id": item.get("face_id"),
                "boundary": item.get("boundary_name"),
                "expected_terminal_count": item.get("expected_terminal_count"),
                "terminal_names": ",".join(item.get("terminal_names", [])),
                "terminal_objects": ",".join(
                    f"{name}:{object_name}"
                    for name, object_name in item.get("terminal_objects", {}).items()
                ),
            }
        )
    display(pd.DataFrame(preview_records))
    display(
        pd.DataFrame(
            [
                {
                    "run_id": "review",
                    "transition": metadata.get("transition_kind"),
                    "lead_length_um": metadata.get("lead_length_um"),
                    "guard_length_um": metadata.get("guard_length_um"),
                    "deembed_length_um": metadata.get("deembed_length_um"),
                    "deembed_mm": metadata.get("deembed_mm_explicit"),
                    "frequency_GHz": "-".join(str(x) for x in metadata.get("frequency_ghz", [])),
                    "metadata_path": str(METADATA_PATH),
                }
            ]
        )
    )


# %% [markdown]
# ## Close

# %%
if RUN_AEDT:
    hfss.save_project()
    if CLOSE_DESKTOP:
        hfss.release_desktop(close_projects=True, close_desktop=True)
        print("AEDT session closed.")
    else:
        print("AEDT project remains open for GUI inspection.")
