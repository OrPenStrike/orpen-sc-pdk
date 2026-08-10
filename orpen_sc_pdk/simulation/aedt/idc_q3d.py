"""Thin public notebook helpers for the OrPen IDC Q3D coupon.

The helper writes the public coupon and AEDT handoff package; the generated
runtime remains the authority for native Q3D import, net assignment, and solve.
The result loader rejects anything except the three-SignalNet Maxwell matrix
used by this coupon.
"""

from __future__ import annotations

import json
import math
import re
import sys
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

import pandas as pd

from orpen_sc_pdk.simulation.aedt.models import (
    AedtNativeCaseSpec,
    AedtNativePackageResult,
    AedtNativePackageSpec,
    AedtRecipeSpec,
    AedtRuntimeSpec,
)
from orpen_sc_pdk.simulation.aedt.package import prepare_aedt_native_handoff_package
from orpen_sc_pdk.tech import METAL_THICKNESS_UM, SUBSTRATE_THICKNESS_UM

_NETS = ("ground", "signal_1", "signal_2")


@dataclass(frozen=True)
class InterdigitalCapacitorQ3dSimulation:
    """One prepared IDC coupon and its generated Q3D package."""

    coupon: object
    package: AedtNativePackageResult
    result_dir: Path

    @property
    def solve_command(self) -> list[str]:
        """Return the headless generated-package solve command."""

        return [
            sys.executable,
            str(self.package.python_script_path),
            "--mode",
            "solve",
            "--non-graphical",
        ]


@dataclass(frozen=True)
class Q3dCapacitanceResult:
    """The accepted full Maxwell result view for the IDC coupon."""

    maxwell: pd.DataFrame
    derived: pd.DataFrame
    summary: pd.DataFrame

    def show(self) -> None:
        """Display the full matrix, derived capacitances, and run identity."""

        from IPython.display import display

        display(self.maxwell)
        display(self.derived)
        display(self.summary)


def prepare_interdigital_capacitor_q3d_simulation(
    *,
    coupon: object,
    run_root: str | Path,
    run_id: str,
    region_padding_um: float,
    setup_name: str = "Setup1",
    matrix_problem_types: tuple[str, ...] = ("C",),
    matrix_types: tuple[str, ...] = ("Maxwell",),
) -> InterdigitalCapacitorQ3dSimulation:
    """Package an already-built finite-ground IDC coupon for three ``SignalNet`` conductors."""

    run_dir = Path(run_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    layers = coupon.info["q3d_coupon"]["layers"]
    signal_1_layer = tuple(int(value) for value in layers["signal_1"])
    signal_2_layer = tuple(int(value) for value in layers["signal_2"])
    ground_layer = tuple(int(value) for value in layers["finite_ground"])
    substrate_layer = tuple(int(value) for value in layers["substrate_footprint"])

    gds_path = run_dir / "interdigital_capacitor_coupon.gds"
    mapping_path = run_dir / "interdigital_capacitor_layer_mapping.json"
    mapping_csv_path = run_dir / "interdigital_capacitor_layer_mapping.csv"
    coupon.write_gds(gds_path)
    mapping_rows = [
        {
            "layer_name": net_name,
            "aedt_layer_number": layer[0],
            "aedt_datatype": layer[1],
            "aedt_layer_tuple": f"{layer[0]}/{layer[1]}",
            "aedt_import_policy": "gds_import",
            "aedt_import_zmin_um": 0.0,
            "aedt_import_thickness_um": METAL_THICKNESS_UM,
            "recommended_aedt_role": "conductor",
            "material": "Al",
            "object_name_base": net_name,
        }
        for net_name, layer in (
            ("signal_1", signal_1_layer),
            ("signal_2", signal_2_layer),
            ("ground", ground_layer),
        )
    ]
    mapping_rows.append(
        {
            "layer_name": "substrate",
            "aedt_layer_number": substrate_layer[0],
            "aedt_datatype": substrate_layer[1],
            "aedt_layer_tuple": f"{substrate_layer[0]}/{substrate_layer[1]}",
            "aedt_import_policy": "gds_import",
            "aedt_import_zmin_um": -SUBSTRATE_THICKNESS_UM,
            "aedt_import_thickness_um": SUBSTRATE_THICKNESS_UM,
            "recommended_aedt_role": "dielectric_volume",
            "material": "Si",
            "object_name_base": "substrate",
        }
    )
    mapping_path.write_text(
        json.dumps(
            {"schema_version": "aedt-layer-mapping.v1", "gds_import_layers": mapping_rows},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    pd.DataFrame(mapping_rows).to_csv(mapping_csv_path, index=False)

    padding = {axis: f"{region_padding_um}um" for axis in ("+X", "-X", "+Y", "-Y", "+Z", "-Z")}
    recipe = AedtRecipeSpec(
        id="capacitance",
        type="q3d_extraction",
        setup_name=setup_name,
        design_name="idc_q3d_capacitance",
        matrix_problem_types=matrix_problem_types,
        matrix_types=matrix_types,
        net_patterns={
            "signal_1": ("signal_1*",),
            "signal_2": ("signal_2*",),
            "ground": ("ground*",),
        },
        modeler_units="um",
        q3d_region={
            "name": "Region",
            "material": "Vacuum",
            "padding_type": "Absolute Offset",
            "padding": padding,
        },
    )
    package = prepare_aedt_native_handoff_package(
        AedtNativePackageSpec(
            project_name="interdigital_capacitor_q3d",
            runtime=AedtRuntimeSpec(version_policy="auto"),
            cases=(
                AedtNativeCaseSpec(
                    id="coupon",
                    gds_path=gds_path,
                    layer_mapping_csv_path=mapping_csv_path,
                    layer_mapping_json_path=mapping_path,
                    recipes=(recipe,),
                ),
            ),
        ),
        package_dir=run_dir / "aedt_native_package",
    )
    return InterdigitalCapacitorQ3dSimulation(
        coupon=coupon,
        package=package,
        result_dir=package.package_dir / "points" / "coupon" / "capacitance",
    )


def load_q3d_capacitance_result(
    simulation: InterdigitalCapacitorQ3dSimulation,
) -> Q3dCapacitanceResult:
    """Load the IDC coupon's exact three-SignalNet Maxwell result."""

    assignment_path = simulation.result_dir / "assignment_summary.json"
    matrix_path = simulation.result_dir / "c_maxwell_matrix.csv"
    metadata_path = simulation.result_dir / "simulation_metadata.json"
    for path in (assignment_path, matrix_path, metadata_path):
        if not path.is_file():
            raise FileNotFoundError(path)

    assignment = json.loads(assignment_path.read_text(encoding="utf-8"))
    readback = assignment.get("readback")
    if (
        assignment.get("ground_net") is not None
        or not isinstance(readback, dict)
        or set(readback) != set(_NETS)
        or any(record.get("type") != "SignalNet" for record in readback.values())
    ):
        raise RuntimeError(
            "IDC Q3D result must read back three SignalNet conductors and no ground net."
        )

    maxwell, unit = _load_maxwell_matrix(matrix_path)
    if (
        maxwell.shape != (3, 3)
        or set(maxwell.index) != set(_NETS)
        or set(maxwell.columns) != set(_NETS)
    ):
        raise RuntimeError(
            "IDC Q3D result must contain the finite 3x3 ground/signal_1/signal_2 Maxwell matrix."
        )
    if not maxwell.map(math.isfinite).all().all():
        raise RuntimeError("IDC Q3D Maxwell matrix contains a non-finite value.")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    timing = {
        record.get("stage"): record.get("elapsed_seconds")
        for record in metadata.get("solve_status", {}).get("stage_timing", [])
    }
    preflight_path = simulation.package.package_dir / "logs" / "aedt_preflight.json"
    preflight = (
        json.loads(preflight_path.read_text(encoding="utf-8")) if preflight_path.is_file() else {}
    )
    derived = pd.DataFrame(
        {
            "capacitance": ("C1G", "C2G", "C12"),
            "value": (
                -maxwell.loc["signal_1", "ground"],
                -maxwell.loc["signal_2", "ground"],
                -maxwell.loc["signal_1", "signal_2"],
            ),
            "unit": unit,
        }
    )
    summary = pd.DataFrame(
        (
            {
                "matrix": "3x3 Maxwell relative to infinity",
                "solve_seconds": timing.get("analyze_setup"),
                "aedt_version": preflight.get("aedt_version"),
                "pyaedt_version": preflight.get("pyaedt_version"),
                "runtime_sha256": metadata.get("source_identity", {}).get(
                    "runtime_bundle_run_aedt_native_py"
                ),
            },
        )
    )
    return Q3dCapacitanceResult(maxwell=maxwell, derived=derived, summary=summary)


def _load_maxwell_matrix(path: Path) -> tuple[pd.DataFrame, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    try:
        table_index = lines.index("Capacitance Matrix")
        units_line = next(line for line in lines if "C Units:" in line)
    except (StopIteration, ValueError) as exc:
        raise RuntimeError(f"Q3D capacitance export is invalid: {path}") from exc
    unit_match = re.search(r"C Units:([^,]+)", units_line)
    if unit_match is None:
        raise RuntimeError(f"Q3D capacitance export has no capacitance unit: {path}")
    matrix = pd.read_csv(StringIO("\n".join(lines[table_index + 1 :])), index_col=0, nrows=3)
    matrix = matrix.loc[:, ~matrix.columns.str.startswith("Unnamed:")]
    matrix.index = matrix.index.astype(str).str.strip()
    matrix.columns = matrix.columns.astype(str).str.strip()
    return matrix.apply(pd.to_numeric, errors="raise"), unit_match.group(1).strip()


__all__ = [
    "InterdigitalCapacitorQ3dSimulation",
    "Q3dCapacitanceResult",
    "load_q3d_capacitance_result",
    "prepare_interdigital_capacitor_q3d_simulation",
]
