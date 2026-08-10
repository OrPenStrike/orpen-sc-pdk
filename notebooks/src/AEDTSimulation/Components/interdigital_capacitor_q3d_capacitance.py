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
# # Interdigital capacitor Q3D capacitance
#
# This public coupon builds one real IDC geometry, packages it for the native
# AEDT runtime, and runs a headless Q3D capacitance extraction when AEDT is
# available.  The saved `.aedt` project remains the GUI-auditable solver
# authority; this notebook only reads its exported matrices after a real solve.

# %%
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

import gdsfactory as gf
import pandas as pd
from gdsfactory import kdb
from IPython.display import HTML, display

import orpen_sc_pdk
from orpen_sc_pdk.cells.capacitor import interdigital_capacitor
from orpen_sc_pdk.simulation.aedt import (
    AedtNativeCaseSpec,
    AedtNativePackageSpec,
    AedtRecipeSpec,
    AedtRuntimeSpec,
    prepare_aedt_native_handoff_package,
    prepare_interdigital_capacitor_q3d_geometry,
)

REPO_ROOT = Path.cwd().resolve()
if not (REPO_ROOT / "orpen_sc_pdk" / "simulation" / "aedt").is_dir():
    raise RuntimeError("Run this notebook from the orpen_sc_pdk repository root.")
orpen_sc_pdk.activate()

# %% [markdown]
# ## Design And Geometry Controls
#
# These values define this one coupon and its diagnostic Q3D setup.  They are
# recorded in the package provenance; none is a scientific acceptance gate.

# %%
RUN_ID = "2026-08-10-idc-q3d-v1"
RUN_ROOT = REPO_ROOT / "build" / "simulation" / "aedt" / "interdigital_capacitor_q3d" / RUN_ID
RUN_SOLVER = False

FINGERS = 20
FINGER_LENGTH_UM = 100.0
FINGER_GAP_UM = 3.3
FINGER_WIDTH_UM = 3.3
TAPER_LENGTH_UM = 150.0
TERMINAL_EXTENSION_LENGTH_UM = 100.0
CAPACITOR_GROUND_GAP_UM = 85.0
TERMINAL_OPEN_CLEARANCE_UM = 25.0
COUPON_MARGIN_UM = 100.0
SUBSTRATE_THICKNESS_UM = 500.0
METAL_THICKNESS_UM = 0.2

# %% [markdown]
# ## Meshing Controls
#
# This coupon has no explicit mesh override.  Its direct-GDS layers define the
# imported elevations and thicknesses; `prepare_interdigital_capacitor_q3d_geometry`
# supplies the IDC terminal openings.

# %%
idc = interdigital_capacitor(
    fingers=FINGERS,
    finger_length=FINGER_LENGTH_UM,
    finger_gap=FINGER_GAP_UM,
    finger_width=FINGER_WIDTH_UM,
    taper_length=TAPER_LENGTH_UM,
    terminal_extension_length_um=TERMINAL_EXTENSION_LENGTH_UM,
    capacitor_ground_gap=CAPACITOR_GROUND_GAP_UM,
)
prepared_idc = prepare_interdigital_capacitor_q3d_geometry(
    idc,
    terminal_open_clearance_um=TERMINAL_OPEN_CLEARANCE_UM,
)

draw_region = prepared_idc.get_region((1, 0), merge=True)
ground_opening = prepared_idc.get_region((110, 0), merge=True)
signal_polygons = sorted(draw_region.each(), key=lambda polygon: polygon.bbox().left)
if len(signal_polygons) != 2 or ground_opening.is_empty():
    raise RuntimeError("Prepared IDC must contain two signal regions and a ground-mask opening.")

coupon_bounds = (draw_region + ground_opening).bbox()
margin_dbu = round(COUPON_MARGIN_UM / prepared_idc.kcl.dbu)
coupon_box = kdb.Box(
    coupon_bounds.left - margin_dbu,
    coupon_bounds.bottom - margin_dbu,
    coupon_bounds.right + margin_dbu,
    coupon_bounds.top + margin_dbu,
)
ground_region = kdb.Region(coupon_box) - ground_opening
if ground_region.is_empty():
    raise RuntimeError("Coupon ground is empty after subtracting the prepared ground-mask opening.")

SIGNAL_1_LAYER = (101, 0)
SIGNAL_2_LAYER = (102, 0)
GROUND_LAYER = (103, 0)
SUBSTRATE_LAYER = (104, 0)
coupon = gf.Component("interdigital_capacitor_q3d_coupon")
coupon.add_polygon(kdb.Region(signal_polygons[0]), layer=SIGNAL_1_LAYER)
coupon.add_polygon(kdb.Region(signal_polygons[1]), layer=SIGNAL_2_LAYER)
coupon.add_polygon(ground_region, layer=GROUND_LAYER)
coupon.add_polygon(kdb.Region(coupon_box), layer=SUBSTRATE_LAYER)
coupon.flatten(merge=True)

display(
    pd.DataFrame(
        (
            {"object": "signal_1", "gds_layer": SIGNAL_1_LAYER, "region_count": 1},
            {"object": "signal_2", "gds_layer": SIGNAL_2_LAYER, "region_count": 1},
            {"object": "ground", "gds_layer": GROUND_LAYER, "region_count": ground_region.count()},
            {"object": "substrate", "gds_layer": SUBSTRATE_LAYER, "region_count": 1},
        )
    )
)

# %%
RUN_ROOT.mkdir(parents=True, exist_ok=True)
GDS_PATH = RUN_ROOT / "interdigital_capacitor_coupon.gds"
MAPPING_PATH = RUN_ROOT / "interdigital_capacitor_layer_mapping.json"
MAPPING_CSV_PATH = RUN_ROOT / "interdigital_capacitor_layer_mapping.csv"
coupon.write_gds(GDS_PATH)

mapping_rows = [
    {
        "layer_name": "signal_1",
        "aedt_layer_number": SIGNAL_1_LAYER[0],
        "aedt_datatype": SIGNAL_1_LAYER[1],
        "aedt_layer_tuple": "101/0",
        "aedt_import_policy": "gds_import",
        "aedt_import_zmin_um": 0.0,
        "aedt_import_thickness_um": METAL_THICKNESS_UM,
        "recommended_aedt_role": "conductor",
        "material": "Al",
        "object_name_base": "signal_1",
    },
    {
        "layer_name": "signal_2",
        "aedt_layer_number": SIGNAL_2_LAYER[0],
        "aedt_datatype": SIGNAL_2_LAYER[1],
        "aedt_layer_tuple": "102/0",
        "aedt_import_policy": "gds_import",
        "aedt_import_zmin_um": 0.0,
        "aedt_import_thickness_um": METAL_THICKNESS_UM,
        "recommended_aedt_role": "conductor",
        "material": "Al",
        "object_name_base": "signal_2",
    },
    {
        "layer_name": "ground",
        "aedt_layer_number": GROUND_LAYER[0],
        "aedt_datatype": GROUND_LAYER[1],
        "aedt_layer_tuple": "103/0",
        "aedt_import_policy": "gds_import",
        "aedt_import_zmin_um": 0.0,
        "aedt_import_thickness_um": METAL_THICKNESS_UM,
        "recommended_aedt_role": "conductor",
        "material": "Al",
        "object_name_base": "ground",
    },
    {
        "layer_name": "substrate",
        "aedt_layer_number": SUBSTRATE_LAYER[0],
        "aedt_datatype": SUBSTRATE_LAYER[1],
        "aedt_layer_tuple": "104/0",
        "aedt_import_policy": "gds_import",
        "aedt_import_zmin_um": -SUBSTRATE_THICKNESS_UM,
        "aedt_import_thickness_um": SUBSTRATE_THICKNESS_UM,
        "recommended_aedt_role": "dielectric_volume",
        "material": "Si",
        "object_name_base": "substrate",
    },
]
mapping_payload = {"schema_version": "aedt-layer-mapping.v1", "gds_import_layers": mapping_rows}
MAPPING_PATH.write_text(
    json.dumps(mapping_payload, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
pd.DataFrame(mapping_rows).to_csv(MAPPING_CSV_PATH, index=False)
display(pd.DataFrame(mapping_rows))

# %% [markdown]
# ## Solver Controls
#
# The direct Q3D runtime imports this GDS with `Q3d.import_gds_3d`, creates the
# diagnostic default setup, assigns the three exact nets, then saves the AEDT
# project.  It exports only the Maxwell and Couple capacitance matrices.

# %%
recipe = AedtRecipeSpec(
    id="capacitance",
    type="q3d_extraction",
    setup_name="Setup1",
    design_name="idc_q3d_capacitance",
    matrix_problem_types=("C",),
    matrix_types=("Maxwell", "Couple"),
    net_patterns={
        "signal_1": ("signal_1*",),
        "signal_2": ("signal_2*",),
        "ground": ("ground*",),
    },
    reference_patterns=("ground*",),
    modeler_units="um",
)
package = prepare_aedt_native_handoff_package(
    AedtNativePackageSpec(
        project_name="interdigital_capacitor_q3d",
        runtime=AedtRuntimeSpec(version_policy="auto"),
        cases=(
            AedtNativeCaseSpec(
                id="coupon",
                gds_path=GDS_PATH,
                layer_mapping_csv_path=MAPPING_CSV_PATH,
                layer_mapping_json_path=MAPPING_PATH,
                recipes=(recipe,),
            ),
        ),
    ),
    package_dir=RUN_ROOT / "aedt_native_package",
)


def package_file_sha256(path: Path) -> str:
    """Return the exact bytes the copied AEDT runtime will consume."""

    return hashlib.sha256(path.read_bytes()).hexdigest()


CURRENT_Q3D_SOURCE_IDENTITY = {
    "gds": package_file_sha256(package.gds_dir / "coupon.gds"),
    "layer_mapping_json": package_file_sha256(
        package.layer_mapping_dir / "coupon_layer_mapping.json"
    ),
    "aedt_material_context": package_file_sha256(
        package.metadata_dir / "coupon_aedt_material_context.json"
    ),
    "runtime_bundle_run_aedt_native_py": package_file_sha256(
        package.scripts_dir / "runtime_bundle" / "run_aedt_native.py"
    ),
}

# %% [markdown]
# ## Output And Run Identity Controls
#
# The portable package and its declared net plan are the handoff identity.

# %%
assignment_plan = {
    "expected_nets": {
        "signal_1": {"object_pattern": "signal_1*", "type": "SignalNet"},
        "signal_2": {"object_pattern": "signal_2*", "type": "SignalNet"},
        "ground": {"object_pattern": "ground*", "type": "GroundNet"},
    },
    "reference_patterns": list(recipe.reference_patterns),
    "runtime": "Q3d.import_gds_3d -> assign_net -> create_setup -> analyze_setup",
}

# %% [markdown]
# ## Data Classification And Provenance
#
# This is a public reusable OrPen simulation workflow.  The provenance record
# binds its package, source revisions, geometry, and runtime versions.

# %%


def source_file_identity(path: Path) -> dict[str, str]:
    """Return the public source identity consumed by this reproducible package."""

    return {
        "path": str(path.relative_to(REPO_ROOT)),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def repository_head() -> str:
    """Return the checked-out source revision used to build this package."""

    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


try:
    import importlib.metadata as importlib_metadata

    PYAEDT_VERSION = importlib_metadata.version("pyaedt")
except importlib_metadata.PackageNotFoundError:
    PYAEDT_VERSION = "unavailable"

provenance = {
    "schema_version": "idc-q3d-notebook-provenance.v1",
    "classification": "public reusable OrPen simulation workflow",
    "geometry_source": {
        "component": "interdigital_capacitor",
        "prepared_by": "prepare_interdigital_capacitor_q3d_geometry",
        "gds_path": str(GDS_PATH),
        "gds_sha256": hashlib.sha256(GDS_PATH.read_bytes()).hexdigest(),
        "parameters": {
            "fingers": FINGERS,
            "finger_length_um": FINGER_LENGTH_UM,
            "finger_gap_um": FINGER_GAP_UM,
            "finger_width_um": FINGER_WIDTH_UM,
            "taper_length_um": TAPER_LENGTH_UM,
            "terminal_extension_length_um": TERMINAL_EXTENSION_LENGTH_UM,
            "terminal_open_clearance_um": TERMINAL_OPEN_CLEARANCE_UM,
            "coupon_margin_um": COUPON_MARGIN_UM,
            "substrate_thickness_um": SUBSTRATE_THICKNESS_UM,
            "metal_thickness_um": METAL_THICKNESS_UM,
        },
    },
    "package": {
        "manifest": str(package.manifest_path),
        "manifest_sha256": hashlib.sha256(package.manifest_path.read_bytes()).hexdigest(),
        "project": str(package.project_path),
        "runtime": recipe.type,
        "setup": recipe.setup_name,
        "matrix_outputs": ["c_maxwell_matrix.csv", "c_couple_matrix.csv"],
    },
    "assignment_plan": assignment_plan,
    "q3d_runtime_source_identity": CURRENT_Q3D_SOURCE_IDENTITY,
    "source_identity": {
        "git_head": repository_head(),
        "files": {
            "capacitor.py": source_file_identity(
                REPO_ROOT / "orpen_sc_pdk" / "cells" / "capacitor.py"
            ),
            "geometry.py": source_file_identity(
                REPO_ROOT / "orpen_sc_pdk" / "simulation" / "aedt" / "geometry.py"
            ),
            "run_aedt_native.py": source_file_identity(
                REPO_ROOT
                / "orpen_sc_pdk"
                / "simulation"
                / "aedt"
                / "runtime_bundle"
                / "run_aedt_native.py"
            ),
        },
    },
    "versions": {
        "python": sys.version,
        "gdsfactory": gf.__version__,
        "pyaedt": PYAEDT_VERSION,
    },
}
(package.metadata_dir / "notebook_provenance.json").write_text(
    json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
display(pd.DataFrame.from_dict(assignment_plan["expected_nets"], orient="index"))

# %% [markdown]
# ## Execution Controls
#
# The headless runtime command is shown below.  A missing AEDT installation
# leaves the real package and assignment plan available without fabricating a
# scientific result.

# %%


def installed_aedt_versions() -> dict[str, str]:
    """Return AEDT installs visible to PyAEDT, without launching a solver."""

    if importlib.util.find_spec("ansys.aedt.core") is None:
        return {}
    from ansys.aedt.core.internal.aedt_versions import aedt_versions

    return dict(aedt_versions.installed_versions)


try:
    AEDT_INSTALLS = installed_aedt_versions()
except Exception as exc:
    AEDT_INSTALLS = {}
    AEDT_STATUS = f"AEDT discovery unavailable: {exc}"
else:
    AEDT_STATUS = "AEDT available" if AEDT_INSTALLS else "AEDT is not installed on this machine"

SOLVE_COMMAND = [
    sys.executable,
    str(package.python_script_path),
    "--mode",
    "solve",
    "--non-graphical",
]
display(HTML(f"<p><b>Runtime status:</b> {AEDT_STATUS}</p><code>{' '.join(SOLVE_COMMAND)}</code>"))
if RUN_SOLVER:
    if not AEDT_INSTALLS:
        display(
            HTML(
                "<p><b>No scientific result:</b> AEDT is absent. The real geometry, package, "
                "and exact assignment plan above are ready for an AEDT machine.</p>"
            )
        )
    else:
        subprocess.run(SOLVE_COMMAND, cwd=package.package_dir, check=True)

# %% [markdown]
# ## Validation And Failure Controls
#
# Matrix-derived capacitance is withheld unless a real solve, both exports, and
# exact assignment readback are present.

# %% [markdown]
# ## Physics Analysis Results
#
# No capacitance is inferred without both real Q3D CSV exports and the runtime
# assignment readback.  Raw matrix units remain those written by AEDT.

# %%
RESULT_DIR = package.package_dir / "results" / "coupon" / "capacitance"
MAXWELL_CSV = RESULT_DIR / "c_maxwell_matrix.csv"
COUPLE_CSV = RESULT_DIR / "c_couple_matrix.csv"
ASSIGNMENT_JSON = RESULT_DIR / "assignment_summary.json"


def read_q3d_matrix(path: Path) -> tuple[pd.DataFrame, dict[str, str]]:
    """Read the title, C units, and one strict AEDT matrix table as printed."""

    if not path.is_file() or path.stat().st_size == 0:
        raise FileNotFoundError(path)
    lines = path.read_text(encoding="utf-8").splitlines()
    unit_line = next((line for line in lines if re.search(r"(?:^|,)\s*C Units:", line)), None)
    if unit_line is None:
        raise RuntimeError(f"Q3D matrix has no C Units line: {path}")
    unit_match = re.search(r"(?:^|,)\s*C Units:([^,]+)", unit_line)
    if unit_match is None or not unit_match.group(1).strip():
        raise RuntimeError(f"Q3D matrix has an invalid C Units line: {unit_line!r}")
    title_index = next(
        (
            index
            for index, line in enumerate(lines)
            if "Matrix" in line and not line.startswith("Reduce")
        ),
        None,
    )
    if title_index is None:
        raise RuntimeError(f"Q3D matrix has no title line: {path}")
    header_index = title_index + 1
    if header_index >= len(lines):
        raise RuntimeError(f"Q3D matrix title has no table header: {path}")
    header = [value.strip() for value in lines[header_index].split(",")]
    labels = header[1:] if header and not header[0] else []
    if not labels or len(labels) != len(set(labels)) or any(not label for label in labels):
        raise RuntimeError(f"Q3D matrix has invalid column labels: {lines[header_index]!r}")
    rows: list[list[str]] = []
    row_labels: list[str] = []
    for line in lines[header_index + 1 :]:
        if not line.strip():
            break
        values = [value.strip() for value in line.split(",")]
        if len(values) != len(labels) + 1 or values[0] not in labels:
            raise RuntimeError(f"Q3D matrix has an invalid row: {line!r}")
        if values[0] in row_labels:
            raise RuntimeError(f"Q3D matrix repeats row {values[0]!r}")
        for value in values[1:]:
            raw_decimal(value)
        row_labels.append(values[0])
        rows.append(values[1:])
    if row_labels != labels:
        raise RuntimeError(f"Q3D matrix rows do not exactly match columns: {row_labels}, {labels}")
    return (
        pd.DataFrame(rows, index=labels, columns=labels, dtype="string"),
        {"title": lines[title_index], "c_units": unit_match.group(1).strip()},
    )


def raw_decimal(value: object) -> Decimal:
    """Parse one printed AEDT number without applying a unit conversion."""

    try:
        return Decimal(str(value).strip())
    except InvalidOperation as exc:
        raise RuntimeError(f"Q3D matrix entry is not a plain numeric value: {value!r}") from exc


def printed_resolution(value: object) -> Decimal:
    """Return the precision implied by AEDT's printed numeric token."""

    return Decimal(1).scaleb(raw_decimal(value).as_tuple().exponent)


def matrix_entry(matrix: pd.DataFrame, row: str, column: str) -> tuple[Decimal, object]:
    raw = matrix.loc[row, column]
    return raw_decimal(raw), raw


def capacitance_from_maxwell(
    matrix: pd.DataFrame, assignment: dict[str, object]
) -> tuple[dict[str, object], dict[str, object]]:
    """Apply the declared full/reduced Maxwell conventions to one real matrix."""

    if assignment.get("ground_net") != "ground":
        raise RuntimeError("Q3D assignment readback does not identify 'ground' as the ground net.")
    assigned = assignment.get("readback")
    if not isinstance(assigned, dict) or set(assigned) != {"signal_1", "signal_2", "ground"}:
        raise RuntimeError("Q3D assignment readback does not prove the exact three requested nets.")
    expected_types = {"signal_1": "SignalNet", "signal_2": "SignalNet", "ground": "GroundNet"}
    requested = assignment.get("requested_objects")
    if not isinstance(requested, dict) or set(requested) != set(expected_types):
        raise RuntimeError("Q3D assignment has no exact requested-object readback.")
    assigned_sets = {}
    for net_name, expected_type in expected_types.items():
        record = assigned.get(net_name)
        if not isinstance(record, dict):
            raise RuntimeError(f"Q3D net {net_name!r} readback is not a mapping.")
        objects = record.get("objects")
        if record.get("type") != expected_type or not isinstance(objects, list) or not objects:
            raise RuntimeError(f"Q3D net {net_name!r} has an incomplete assignment readback.")
        if sorted(objects) != sorted(requested.get(net_name, [])):
            raise RuntimeError(f"Q3D net {net_name!r} readback differs from its requested objects.")
        assigned_sets[net_name] = set(objects)
    if any(
        assigned_sets[left].intersection(assigned_sets[right])
        for left, right in (
            ("signal_1", "signal_2"),
            ("signal_1", "ground"),
            ("signal_2", "ground"),
        )
    ):
        raise RuntimeError("Q3D assignment readback has overlapping net object sets.")
    labels = set(matrix.index)
    if labels != set(matrix.columns):
        raise RuntimeError(
            f"Q3D Maxwell row/column labels disagree: rows={matrix.index}, cols={matrix.columns}"
        )

    signal_labels = {"signal_1", "signal_2"}
    if labels == signal_labels | {"ground"} and matrix.shape == (3, 3):
        representation = "A_full_three_net"
        diagonal = {label: matrix_entry(matrix, label, label)[0] for label in labels}
        off_diagonal = [
            matrix_entry(matrix, row, column)[0]
            for row in labels
            for column in labels
            if row != column
        ]
        if any(value <= 0 for value in diagonal.values()) or any(
            value > 0 for value in off_diagonal
        ):
            raise RuntimeError(
                "Full Q3D Maxwell matrix does not satisfy the declared Q = M V sign convention."
            )
        c12, raw_c12 = matrix_entry(matrix, "signal_1", "signal_2")
        c1g, raw_c1g = matrix_entry(matrix, "signal_1", "ground")
        c2g, raw_c2g = matrix_entry(matrix, "signal_2", "ground")
        capacitance = {"C12": -c12, "C1G": -c1g, "C2G": -c2g}
        raw_entries = {"M12": raw_c12, "M1G": raw_c1g, "M2G": raw_c2g}
        convention = "C12=-M12; C1G=-M1G; C2G=-M2G"
    elif labels == signal_labels and matrix.shape == (2, 2):
        representation = "B_reduced_two_signal"
        m11, raw_m11 = matrix_entry(matrix, "signal_1", "signal_1")
        m22, raw_m22 = matrix_entry(matrix, "signal_2", "signal_2")
        m12, raw_m12 = matrix_entry(matrix, "signal_1", "signal_2")
        m21, raw_m21 = matrix_entry(matrix, "signal_2", "signal_1")
        if m11 <= 0 or m22 <= 0 or m12 > 0 or m21 > 0:
            raise RuntimeError(
                "Reduced Q3D Maxwell matrix does not satisfy the declared Q = M V sign convention."
            )
        tolerance = max(printed_resolution(raw_m12), printed_resolution(raw_m21))
        if abs(m12 - m21) > tolerance:
            raise RuntimeError(
                f"Reduced Q3D off-diagonals disagree beyond printed resolution: {m12}, {m21}; "
                f"resolution={tolerance}"
            )
        symmetric = (m12 + m21) / 2
        capacitance = {"C12": -symmetric, "C1G": m11 + symmetric, "C2G": m22 + symmetric}
        raw_entries = {"M11": raw_m11, "M22": raw_m22, "M12": raw_m12, "M21": raw_m21}
        convention = "C12=-sym(M12,M21); C1G=M11+sym(M12,M21); C2G=M22+sym(M12,M21)"
    else:
        raise RuntimeError(
            "Unsupported Q3D Maxwell representation; expected exactly full "
            "{signal_1, signal_2, ground} 3x3 or reduced {signal_1, signal_2} 2x2. "
            f"Got labels={sorted(labels)}, shape={matrix.shape}."
        )
    return (
        {
            "representation": representation,
            "convention": convention,
            "capacitance_raw_aedt_units": {key: str(value) for key, value in capacitance.items()},
            "raw_matrix_entries": {key: str(value) for key, value in raw_entries.items()},
        },
        {"labels": sorted(labels), "shape": list(matrix.shape)},
    )


result_metadata = (
    json.loads((RESULT_DIR / "simulation_metadata.json").read_text(encoding="utf-8"))
    if (RESULT_DIR / "simulation_metadata.json").is_file()
    else {}
)
result_reasons = []
if not isinstance(result_metadata, dict):
    result_reasons.append("result metadata is not a mapping")
    result_metadata = {}
solve_status = result_metadata.get("solve_status")
analyze_setup = solve_status.get("analyze_setup") if isinstance(solve_status, dict) else None
if not isinstance(analyze_setup, dict) or not analyze_setup.get("return_value"):
    result_reasons.append("a successful Q3D analyze_setup record is absent")
if result_metadata.get("source_identity") != CURRENT_Q3D_SOURCE_IDENTITY:
    result_reasons.append("result source identity does not match the regenerated package")
setup_metadata = result_metadata.get("setup")
if (
    not isinstance(setup_metadata, dict)
    or setup_metadata.get("requested_options") != recipe.setup_options
):
    result_reasons.append("result setup options do not match the current recipe")
real_solve = not result_reasons
if MAXWELL_CSV.is_file() and COUPLE_CSV.is_file() and ASSIGNMENT_JSON.is_file() and real_solve:
    maxwell, maxwell_metadata = read_q3d_matrix(MAXWELL_CSV)
    couple, couple_metadata = read_q3d_matrix(COUPLE_CSV)
    assignment_readback = json.loads(ASSIGNMENT_JSON.read_text(encoding="utf-8"))
    capacitance, matrix_audit = capacitance_from_maxwell(maxwell, assignment_readback)
    derived = pd.DataFrame(
        (
            {
                "quantity": "C1G",
                "node_definition": "signal_1 to ground",
                "value": capacitance["capacitance_raw_aedt_units"]["C1G"],
                "unit": maxwell_metadata["c_units"],
                "source_matrix": "Maxwell",
                "sign_convention": capacitance["convention"],
            },
            {
                "quantity": "C2G",
                "node_definition": "signal_2 to ground",
                "value": capacitance["capacitance_raw_aedt_units"]["C2G"],
                "unit": maxwell_metadata["c_units"],
                "source_matrix": "Maxwell",
                "sign_convention": capacitance["convention"],
            },
            {
                "quantity": "C12",
                "node_definition": "signal_1 to signal_2",
                "value": capacitance["capacitance_raw_aedt_units"]["C12"],
                "unit": maxwell_metadata["c_units"],
                "source_matrix": "Maxwell",
                "sign_convention": capacitance["convention"],
            },
        )
    )
    derived_csv = RESULT_DIR / "capacitance_derived.csv"
    derived.to_csv(derived_csv, index=False)
    preflight_path = package.package_dir / "logs" / "aedt_preflight.json"
    if not preflight_path.is_file():
        raise RuntimeError("Real Q3D solve has no AEDT preflight record.")
    analysis = {
        "schema_version": "idc-q3d-capacitance-analysis.v1",
        "maxwell_csv": str(MAXWELL_CSV),
        "couple_csv_audit_only": str(COUPLE_CSV),
        "assignment_readback": assignment_readback,
        "maxwell": {**matrix_audit, **maxwell_metadata},
        "couple_audit": {
            "labels": list(couple.columns),
            "shape": list(couple.shape),
            **couple_metadata,
        },
        "derived_csv": str(derived_csv),
        "aedt_preflight": json.loads(preflight_path.read_text(encoding="utf-8")),
        **capacitance,
    }
    (RESULT_DIR / "capacitance_analysis.json").write_text(
        json.dumps(analysis, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    display(
        HTML(
            f"<h3>Maxwell matrix — {maxwell_metadata['title']} ({maxwell_metadata['c_units']})</h3>"
        )
    )
    display(maxwell)
    display(
        HTML(f"<h3>Couple matrix — {couple_metadata['title']} ({couple_metadata['c_units']})</h3>")
    )
    display(couple)
    display(HTML("<h3>Derived capacitances</h3>"))
    display(derived)
    display(
        HTML(
            "<p><b>Q3D matrix interpretation:</b> "
            f"{analysis['representation']}; {analysis['convention']}. "
            "Couple matrix is recorded for audit only and is never a fallback.</p>"
        )
    )
else:
    missing_artifacts = [
        path.name for path in (MAXWELL_CSV, COUPLE_CSV, ASSIGNMENT_JSON) if not path.is_file()
    ]
    if missing_artifacts:
        result_reasons.append(f"missing {', '.join(missing_artifacts)}")
    display(
        HTML(
            "<p><b>No scientific result:</b> "
            f"{' ; '.join(result_reasons)}. No capacitance is displayed.</p>"
        )
    )

# %% [markdown]
# ## Simulation Performance / Benchmarks
#
# When a solve runs, the runtime records stage timing and benchmark exports in
# `simulation_metadata.json`.  These are operational diagnostics, not solver
# convergence eligibility criteria.

# %%
METADATA_JSON = RESULT_DIR / "simulation_metadata.json"
if METADATA_JSON.is_file():
    metadata = json.loads(METADATA_JSON.read_text(encoding="utf-8"))
    timing = metadata.get("solve_status", {}).get("stage_timing", [])
    display(pd.DataFrame(timing))
    display(pd.DataFrame(metadata.get("solve_status", {}).get("benchmark_exports", [])))
else:
    display(HTML("<p>Performance records appear after a real Q3D solve.</p>"))
