"""Export solved D3 flip-gap Q2D artifacts and strict tolerance manifests."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory

from export_orpen_q2d_intrinsic_purcell_cases import export_cases

HEIGHTS_UM = tuple(round(6.0 + 0.1 * index, 1) for index in range(31))
NOMINAL_HEIGHTS_UM = (7.0, 8.0)
MANIFEST_SCHEMA = "d3-q2d-fabrication-tolerance-input.v1"


def _slug(height_um: float) -> str:
    return f"{height_um:.1f}".replace(".", "p")


def _case_id(role: str, height_um: float) -> str:
    return f"{role}__gap_{_slug(height_um)}um"


def _artifact_name(role: str) -> str:
    return (
        "coupled_pair_maxwell_lc.json"
        if role == "coupled_pair"
        else "single_reference_maxwell_lc.json"
    )


def _validate_artifact(path: Path, role: str, height_um: float) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload.get("cases")
    if payload.get("artifact_status") != "complete" or not isinstance(cases, list):
        raise ValueError(f"Incomplete Q2D artifact: {path}")
    if len(cases) != 1 or cases[0].get("case_role") != role:
        raise ValueError(f"Q2D artifact has the wrong case role: {path}")
    actual_height = cases[0].get("parameters", {}).get("flip_chip_gap_height_um")
    if not math.isclose(float(actual_height), height_um, rel_tol=0.0, abs_tol=1.0e-12):
        raise ValueError(
            f"Q2D artifact height mismatch at {path}: expected {height_um}, got {actual_height}"
        )


def _manifest(nominal_height_um: float) -> dict[str, object]:
    heights = tuple(
        height
        for height in HEIGHTS_UM
        if nominal_height_um - 1.0 <= height <= nominal_height_um + 1.0
    )
    if len(heights) != 21:
        raise AssertionError(f"Expected 21 heights around {nominal_height_um}")
    return {
        "schema_version": MANIFEST_SCHEMA,
        "q2d_sweeps": [
            {
                "id": "flip_chip_gap_height",
                "parameter": "flip_chip_gap_height_um",
                "nominal_value": nominal_height_um,
                "unit": "um",
                "points": [
                    {
                        "value": height,
                        "pair_path": (f"gap_{_slug(height)}um/coupled_pair_maxwell_lc.json"),
                        "single_path": (f"gap_{_slug(height)}um/single_reference_maxwell_lc.json"),
                    }
                    for height in heights
                ],
            }
        ],
    }


def export_tolerance_artifacts(run_root: Path, output_dir: Path) -> tuple[Path, ...]:
    """Validate all 62 solves before publishing artifacts or manifests."""

    run_root = run_root.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    with TemporaryDirectory(prefix=".d3-gap-export-", dir=output_dir) as temporary:
        staging = Path(temporary)
        staged_artifacts: list[tuple[Path, Path]] = []
        for height_um in HEIGHTS_UM:
            gap_dir = f"gap_{_slug(height_um)}um"
            for role in ("coupled_pair", "single_reference"):
                staged = staging / gap_dir / _artifact_name(role)
                export_cases(
                    run_root,
                    staged,
                    case_ids=(_case_id(role, height_um),),
                )
                _validate_artifact(staged, role, height_um)
                staged_artifacts.append((staged, output_dir / gap_dir / staged.name))

        staged_manifests: list[tuple[Path, Path]] = []
        for nominal_height_um in NOMINAL_HEIGHTS_UM:
            name = f"flip_gap_tolerance_nominal_{_slug(nominal_height_um)}um.json"
            staged = staging / name
            staged.write_text(
                json.dumps(_manifest(nominal_height_um), indent=2) + "\n",
                encoding="utf-8",
            )
            staged_manifests.append((staged, output_dir / name))

        for staged, destination in staged_artifacts:
            destination.parent.mkdir(parents=True, exist_ok=True)
            staged.replace(destination)
        for staged, destination in staged_manifests:
            staged.replace(destination)

    return tuple(destination for _, destination in staged_manifests)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Defaults to RUN_ROOT/artifacts.",
    )
    args = parser.parse_args()
    output_dir = args.output_dir or args.run_root / "artifacts"
    manifests = export_tolerance_artifacts(args.run_root, output_dir)
    print(json.dumps({"manifests": [str(path) for path in manifests]}, indent=2))


if __name__ == "__main__":
    main()
