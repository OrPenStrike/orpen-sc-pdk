"""Build the public D3 flip-chip-gap tolerance Q2D package."""

from __future__ import annotations

import argparse
import csv
import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from build_d3_same_face_ground_clearance_q2d_package import (
    ADAPTIVE_FREQUENCY,
    AIR_HEIGHT_UM,
    D0_DIE_THICKNESS_UM,
    D1_DIE_THICKNESS_UM,
    GROUND_WIDTH_UM,
    METAL_THICKNESS_UM,
    TRACE_GAP_UM,
    TRACE_WIDTH_UM,
    _atomic_write_text,
)

from orpen_sc_pdk.simulation.aedt.models import (
    AedtNativeCaseSpec,
    AedtNativePackageSpec,
    AedtQ2dSetupSpec,
    AedtRecipeSpec,
)
from orpen_sc_pdk.simulation.aedt.package import prepare_aedt_native_handoff_package
from orpen_sc_pdk.simulation.aedt.q2d import (
    make_q2d_same_face_single_trace_cross_section,
    make_q2d_same_face_two_trace_cross_section,
    write_q2d_cross_section_payload,
)

PROJECT_NAME = "d3_flip_gap_tolerance_q2d"
INTER_TRACE_GROUND_WIDTH_UM = 5.5
UPPER_GROUND_CLEARANCE_WIDTH_UM = 60.0
FLIP_CHIP_GAP_HEIGHTS_UM = tuple(round(6.0 + 0.1 * index, 1) for index in range(31))


def _height_slug(height_um: float) -> str:
    return f"{height_um:.1f}".replace(".", "p")


def _scale_slug(scale: float) -> str:
    return f"{scale:.2f}".replace(".", "p")


def _case_id(
    role: str,
    height_um: float,
    clearance_um: float,
    qualifier: str | None = None,
) -> str:
    suffix = "__d1_ground_continuous" if clearance_um == 0.0 else ""
    qualifier_suffix = "" if qualifier is None else f"__{qualifier}"
    return f"{role}__gap_{_height_slug(height_um)}um{qualifier_suffix}{suffix}"


def _point_row(
    run_id: str,
    role: str,
    height_um: float,
    clearance_um: float,
    trace_width_um: float,
    trace_gap_um: float,
    inter_trace_ground_width_um: float | None,
    lateral_scale: float | None,
    qualifier: str | None,
) -> dict[str, object]:
    case_id = _case_id(role, height_um, clearance_um, qualifier)
    return {
        "point_slug": case_id,
        "run_id": run_id,
        "parameter_id": case_id,
        "parameter_case_role": role,
        "parameter_trace_width_um": trace_width_um,
        "parameter_trace_gap_um": trace_gap_um,
        "parameter_inter_trace_ground_width_um": inter_trace_ground_width_um,
        "parameter_lateral_scale": lateral_scale,
        "parameter_upper_ground_clearance_width_um": clearance_um,
        "parameter_flip_chip_gap_height_um": height_um,
        "parameter_d0_die_thickness_um": D0_DIE_THICKNESS_UM,
        "parameter_d1_die_thickness_um": D1_DIE_THICKNESS_UM,
        "parameter_air_height_um": AIR_HEIGHT_UM,
        "parameter_ground_width_um": GROUND_WIDTH_UM,
        "parameter_metal_thickness_um": METAL_THICKNESS_UM,
        "parameter_adaptive_frequency": ADAPTIVE_FREQUENCY,
    }


def build_package(
    run_root: Path,
    *,
    heights_um: tuple[float, ...] = FLIP_CHIP_GAP_HEIGHTS_UM,
    upper_ground_clearance_width_um: float = UPPER_GROUND_CLEARANCE_WIDTH_UM,
    trace_width_um: float = TRACE_WIDTH_UM,
    trace_gap_um: float = TRACE_GAP_UM,
    inter_trace_ground_widths_um: tuple[float, ...] = (INTER_TRACE_GROUND_WIDTH_UM,),
    lateral_scales: tuple[float, ...] = (),
    screen_trace_gaps_um: tuple[float, ...] = (),
):
    if run_root.exists():
        raise FileExistsError(run_root)
    if not heights_um:
        raise ValueError("At least one flip-chip height is required.")
    if lateral_scales and len(inter_trace_ground_widths_um) != 1:
        raise ValueError("lateral_scales cannot be combined with an inter-trace-ground sweep.")
    if screen_trace_gaps_um and (lateral_scales or len(inter_trace_ground_widths_um) != 1):
        raise ValueError(
            "screen_trace_gaps_um requires one fixed inter-trace ground and no lateral-scale sweep."
        )
    geometries = (
        [
            (
                trace_width_um,
                gap_um,
                inter_trace_ground_widths_um[0],
                None,
                f"s_{_scale_slug(gap_um)}um",
            )
            for gap_um in screen_trace_gaps_um
        ]
        if screen_trace_gaps_um
        else [
            (
                trace_width_um * scale,
                trace_gap_um * scale,
                inter_trace_ground_widths_um[0] * scale,
                scale,
                f"scale_{_scale_slug(scale)}",
            )
            for scale in lateral_scales
        ]
        if lateral_scales
        else [
            (
                trace_width_um,
                trace_gap_um,
                inter_trace_ground_width_um,
                None,
                (
                    f"d_{_height_slug(inter_trace_ground_width_um)}um"
                    if len(inter_trace_ground_widths_um) > 1
                    else None
                ),
            )
            for inter_trace_ground_width_um in inter_trace_ground_widths_um
        ]
    )
    pair_rows = [
        _point_row(
            run_root.name,
            "coupled_pair",
            height_um,
            upper_ground_clearance_width_um,
            width_um,
            gap_um,
            inter_ground_um,
            scale,
            qualifier,
        )
        for height_um in heights_um
        for width_um, gap_um, inter_ground_um, scale, qualifier in geometries
    ]
    single_geometries = geometries if lateral_scales or screen_trace_gaps_um else [geometries[0]]
    rows = pair_rows + [
        _point_row(
            run_root.name,
            "single_reference",
            height_um,
            upper_ground_clearance_width_um,
            width_um,
            gap_um,
            None,
            scale,
            qualifier,
        )
        for height_um in heights_um
        for width_um, gap_um, _, scale, qualifier in single_geometries
    ]
    recipe = AedtRecipeSpec(
        id="q2d",
        type="q2d_extraction",
        q2d_geometry_mode="semantic_cross_section",
        section_plane="XY",
        matrix_problem_types=("CG", "RL"),
        matrix_types=("Maxwell",),
        q2d_setup=AedtQ2dSetupSpec(adaptive_frequency=ADAPTIVE_FREQUENCY),
    )
    with TemporaryDirectory(prefix="orpen-d3-gap-tolerance-") as temporary_directory:
        source_dir = Path(temporary_directory)
        cases = []
        for row in rows:
            role = str(row["parameter_case_role"])
            height_um = float(row["parameter_flip_chip_gap_height_um"])
            common = {
                "trace_width_um": float(row["parameter_trace_width_um"]),
                "trace_gap_um": float(row["parameter_trace_gap_um"]),
                "upper_ground_clearance_width_um": upper_ground_clearance_width_um,
                "flip_chip_gap_height_um": height_um,
                "die_thickness_um": D0_DIE_THICKNESS_UM,
                "air_height_um": AIR_HEIGHT_UM,
                "ground_width_um": GROUND_WIDTH_UM,
                "metal_thickness_um": METAL_THICKNESS_UM,
            }
            cross_section = (
                make_q2d_same_face_two_trace_cross_section(
                    **common,
                    inter_trace_ground_width_um=float(row["parameter_inter_trace_ground_width_um"]),
                )
                if role == "coupled_pair"
                else make_q2d_same_face_single_trace_cross_section(**common)
            )
            case_id = str(row["point_slug"])
            sidecar = write_q2d_cross_section_payload(
                source_dir / f"{case_id}_q2d_cross_section.json",
                cross_section,
            )
            cases.append(
                AedtNativeCaseSpec(
                    id=case_id,
                    q2d_cross_section_json_path=sidecar,
                    recipes=(recipe,),
                )
            )
        result = prepare_aedt_native_handoff_package(
            AedtNativePackageSpec(
                project_name=PROJECT_NAME,
                point_local_sweep=True,
                cases=tuple(cases),
            ),
            package_dir=run_root,
        )

    _atomic_write_text(
        run_root / "points.json",
        json.dumps(
            {
                "schema_version": "aedt-q2d-sweep-points.v1",
                "sweep_contract": (
                    "d3-flip-gap-continuous-upper-ground-q2d.v1"
                    if upper_ground_clearance_width_um == 0.0
                    else "d3-flip-gap-tolerance-q2d.v1"
                ),
                "points": rows,
            },
            indent=2,
        )
        + "\n",
    )
    header = list(rows[0])
    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=header)
    writer.writeheader()
    writer.writerows(rows)
    _atomic_write_text(run_root / "points.csv", buffer.getvalue())
    _atomic_write_text(
        run_root / "metadata" / "d3_flip_gap_tolerance_package_audit.json",
        json.dumps(
            {
                "schema_version": "d3-flip-gap-tolerance-q2d-package-audit.v1",
                "status": "package_ready_solver_pending",
                "case_count": len(rows),
                "flip_chip_gap_heights_um": heights_um,
                "fixed_public_geometry_um": {
                    "trace_width": trace_width_um,
                    "trace_gap": trace_gap_um,
                    "inter_trace_ground_widths": inter_trace_ground_widths_um,
                    "lateral_scales": lateral_scales,
                    "screen_trace_gaps": screen_trace_gaps_um,
                    "upper_ground_clearance_width": upper_ground_clearance_width_um,
                    "upper_ground_metal_policy": (
                        "continuous_over_full_modeled_lateral_extent"
                        if upper_ground_clearance_width_um == 0.0
                        else "removed_only_within_local_clearance"
                    ),
                },
            },
            indent=2,
        )
        + "\n",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument(
        "--height-um",
        action="append",
        type=float,
        help="Restrict the package to one or more explicit heights.",
    )
    parser.add_argument(
        "--upper-ground-clearance-width-um",
        type=float,
        default=UPPER_GROUND_CLEARANCE_WIDTH_UM,
        help="Use zero for a continuous, unexcavated D1 bottom ground.",
    )
    parser.add_argument("--trace-width-um", type=float, default=TRACE_WIDTH_UM)
    parser.add_argument("--trace-gap-um", type=float, default=TRACE_GAP_UM)
    parser.add_argument(
        "--base-inter-trace-ground-width-um",
        type=float,
        default=INTER_TRACE_GROUND_WIDTH_UM,
    )
    parser.add_argument(
        "--inter-trace-ground-width-um",
        action="append",
        type=float,
        help="Repeat to screen more than one MTL center-ground width.",
    )
    parser.add_argument(
        "--lateral-scale",
        action="append",
        type=float,
        help="Repeat to scale trace width, CPW gap, and MTL center ground together.",
    )
    parser.add_argument(
        "--screen-trace-gap-um",
        action="append",
        type=float,
        help="Repeat to screen CPW gaps at one fixed trace and center-ground width.",
    )
    args = parser.parse_args()
    if args.lateral_scale is not None and args.inter_trace_ground_width_um is not None:
        parser.error("--lateral-scale cannot be combined with --inter-trace-ground-width-um.")
    if args.screen_trace_gap_um is not None and (
        args.lateral_scale is not None or args.inter_trace_ground_width_um is not None
    ):
        parser.error(
            "--screen-trace-gap-um cannot be combined with lateral-scale or "
            "inter-trace-ground sweeps."
        )
    heights_um = tuple(args.height_um) if args.height_um is not None else FLIP_CHIP_GAP_HEIGHTS_UM
    result = build_package(
        args.run_root,
        heights_um=heights_um,
        upper_ground_clearance_width_um=args.upper_ground_clearance_width_um,
        trace_width_um=args.trace_width_um,
        trace_gap_um=args.trace_gap_um,
        inter_trace_ground_widths_um=(
            tuple(args.inter_trace_ground_width_um)
            if args.inter_trace_ground_width_um is not None
            else (args.base_inter_trace_ground_width_um,)
        ),
        lateral_scales=(tuple(args.lateral_scale) if args.lateral_scale is not None else ()),
        screen_trace_gaps_um=(
            tuple(args.screen_trace_gap_um) if args.screen_trace_gap_um is not None else ()
        ),
    )
    print(json.dumps({"run_root": str(result.package_dir), "cases": result.case_count}))


if __name__ == "__main__":
    main()
