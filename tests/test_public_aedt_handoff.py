from __future__ import annotations

import json
import tarfile
from pathlib import Path

import pytest
import yaml

import orpen_sc_pdk.simulation.aedt as public_aedt
from orpen_sc_pdk.simulation import (
    AedtHpcProfileSpec,
    AedtHpcValidationSpec,
    AedtNativeCaseSpec,
    AedtNativePackageSpec,
    AedtQ2dMatrixProblemType,
    AedtQ3dMatrixProblemType,
    AedtRecipeSpec,
    package_aedt_native_handoff,
    prepare_aedt_native_handoff_package,
)


def test_private_repo_can_generate_aedt_handoff_with_custom_profile(tmp_path: Path) -> None:
    source_dir = tmp_path / "private_artifacts"
    source_dir.mkdir()
    _write_public_aedt_case_artifacts(source_dir, "cpw")

    profile = AedtHpcProfileSpec(
        profile_name="private-lab-node",
        resource_defaults={
            "machine_name": "workstation-a",
            "num_cores": 16,
            "max_workers": 2,
            "memory_mb_per_worker": 96000,
        },
        validation=AedtHpcValidationSpec(core_budget=32, memory_mb_total=256000),
    )
    spec = AedtNativePackageSpec(
        project_name="private_cpw",
        hpc_profile=profile,
        cases=(
            AedtNativeCaseSpec(
                id="cpw",
                gds_path=source_dir / "cpw.gds",
                tech_path=source_dir / "cpw.tech",
                control_path=source_dir / "cpw.xml",
                layer_mapping_json_path=source_dir / "cpw_layer_mapping.json",
                source_metadata_path=source_dir / "cpw_cross_section.json",
                q2d_conductors_json_path=source_dir / "cpw_q2d_conductors.json",
                recipes=(
                    AedtRecipeSpec(
                        id="q2d",
                        type="q2d_extraction",
                        assignment_source="q2d_conductors",
                        q2d_geometry_mode="native_2d",
                    ),
                ),
            ),
        ),
    )

    result = prepare_aedt_native_handoff_package(
        spec,
        package_dir=tmp_path / "exports" / "aedt_native",
    )
    manifest = yaml.safe_load(result.manifest_path.read_text(encoding="utf-8"))
    material_context = json.loads(
        (result.metadata_dir / "cpw_aedt_material_context.json").read_text(encoding="utf-8")
    )

    assert manifest["hpc"]["profile"] == "private-lab-node"
    assert manifest["hpc"]["resource"]["machine_name"] == "workstation-a"
    assert manifest["hpc"]["resource"]["worker_core_total"] == 32
    assert manifest["hpc"]["resource"]["ram_percent_resolved"] == 37
    assert manifest["cases"][0]["q2d_conductors"] == "metadata/cpw_q2d_conductors.json"
    assert manifest["cases"][0]["source_metadata"] == "metadata/cpw_cross_section.json"
    assert {binding["aedt_material_name"] for binding in material_context["bindings"]} == {
        "pec",
        "Silicon",
    }
    assert "from ansys.aedt.core" in result.readme_path.read_text(encoding="utf-8")
    assert "PyAEDT" in result.python_script_path.read_text(encoding="utf-8")

    archive = package_aedt_native_handoff(result)

    with tarfile.open(archive.archive_path, "r:gz") as tar:
        names = set(tar.getnames())
    assert any(Path(name).name == "manifest.yaml" for name in names)
    assert any(name.endswith("scripts/run_aedt_native.py") for name in names)


def test_native_2d_handoff_fails_before_package_when_metadata_is_not_runtime_ready(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "private_artifacts"
    source_dir.mkdir()
    _write_public_aedt_case_artifacts(source_dir, "cpw")
    source_dir.joinpath("cpw_cross_section.json").write_text(
        json.dumps(
            {
                "point_slug": "cpw",
                "case_kind": "public_cpw",
                "parameters": {"cpw_width_um": 10.0, "cpw_gap_um": 6.0},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    spec = AedtNativePackageSpec(
        project_name="bad_native_2d",
        cases=(
            AedtNativeCaseSpec(
                id="cpw",
                gds_path=source_dir / "cpw.gds",
                tech_path=source_dir / "cpw.tech",
                control_path=source_dir / "cpw.xml",
                layer_mapping_json_path=source_dir / "cpw_layer_mapping.json",
                source_metadata_path=source_dir / "cpw_cross_section.json",
                q2d_conductors_json_path=source_dir / "cpw_q2d_conductors.json",
                recipes=(
                    AedtRecipeSpec(
                        id="q2d",
                        type="q2d_extraction",
                        assignment_source="q2d_conductors",
                        q2d_geometry_mode="native_2d",
                    ),
                ),
            ),
        ),
    )

    with pytest.raises(ValueError, match="native_2d.*flip-chip"):
        prepare_aedt_native_handoff_package(spec, package_dir=tmp_path / "exports/aedt_native")


def test_aedt_scaffold_keeps_public_solver_boundaries_fail_fast() -> None:
    from orpen_sc_pdk.simulation.aedt.models import AedtRecipeType
    from orpen_sc_pdk.simulation.aedt.package import prepare_aedt_native_handoff_package
    from orpen_sc_pdk.simulation.aedt.runtime_bundle import (
        create_aedt_session,
        load_manifest,
        register_aedt_materials,
        run_point_local_sweep,
    )
    from orpen_sc_pdk.simulation.aedt.runtime_bundle.solver.hfss.driven_terminal import (
        run_hfss_driven_terminal,
    )
    from orpen_sc_pdk.simulation.aedt.runtime_bundle.solver.hfss.eigenmode import (
        run_hfss_eigenmode,
    )
    from orpen_sc_pdk.simulation.aedt.runtime_bundle.solver.q2d.assignment import (
        assign_q2d_conductors,
    )
    from orpen_sc_pdk.simulation.aedt.runtime_bundle.solver.q2d.audit import write_q2d_audit
    from orpen_sc_pdk.simulation.aedt.runtime_bundle.solver.q2d.export import (
        export_q2d_results,
    )
    from orpen_sc_pdk.simulation.aedt.runtime_bundle.solver.q2d.geometry import (
        build_q2d_geometry,
    )
    from orpen_sc_pdk.simulation.aedt.runtime_bundle.solver.q2d.region import (
        create_q2d_region,
    )
    from orpen_sc_pdk.simulation.aedt.runtime_bundle.solver.q2d.setup import create_q2d_setup
    from orpen_sc_pdk.simulation.aedt.runtime_bundle.solver.q2d.solve import solve_q2d
    from orpen_sc_pdk.simulation.aedt.runtime_bundle.solver.q2d.state import (
        validate_q2d_state,
    )
    from orpen_sc_pdk.simulation.aedt.runtime_bundle.solver.q2d.workflow import (
        run_q2d_workflow,
    )
    from orpen_sc_pdk.simulation.aedt.runtime_bundle.solver.q3d import run_q3d_extraction

    scaffold_root = Path(public_aedt.__file__).parent / "runtime_bundle"
    aedt_root = Path(public_aedt.__file__).parent
    expected_scaffold = {
        "io.py",
        "materials.py",
        "session.py",
        "sweep.py",
        "solver/hfss/driven_terminal.py",
        "solver/hfss/eigenmode.py",
        "solver/q3d.py",
        "solver/q2d/workflow.py",
        "solver/q2d/state.py",
        "solver/q2d/geometry.py",
        "solver/q2d/assignment.py",
        "solver/q2d/region.py",
        "solver/q2d/setup.py",
        "solver/q2d/solve.py",
        "solver/q2d/export.py",
        "solver/q2d/audit.py",
    }

    assert repr(public_aedt.AedtRecipeType) == repr(AedtRecipeType)
    assert public_aedt.prepare_aedt_native_handoff_package is prepare_aedt_native_handoff_package
    assert repr(AedtQ2dMatrixProblemType) == repr(public_aedt.AedtQ2dMatrixProblemType)
    assert repr(AedtQ3dMatrixProblemType) == repr(public_aedt.AedtQ3dMatrixProblemType)
    assert not (aedt_root / "native.py").exists()
    assert all((scaffold_root / relative).is_file() for relative in expected_scaffold)

    fail_fast_calls = (
        lambda: load_manifest("manifest.yaml"),
        lambda: register_aedt_materials(),
        lambda: create_aedt_session(),
        lambda: run_point_local_sweep(),
        lambda: run_hfss_driven_terminal({}),
        lambda: run_hfss_eigenmode({}),
        lambda: run_q3d_extraction({}),
        lambda: run_q2d_workflow({}),
        lambda: validate_q2d_state(),
        lambda: build_q2d_geometry(),
        lambda: assign_q2d_conductors(),
        lambda: create_q2d_region(),
        lambda: create_q2d_setup(),
        lambda: solve_q2d(),
        lambda: export_q2d_results(),
        lambda: write_q2d_audit(),
    )
    for call in fail_fast_calls:
        with pytest.raises(NotImplementedError):
            call()


def _write_public_aedt_case_artifacts(directory: Path, stem: str) -> None:
    directory.joinpath(f"{stem}.gds").write_bytes(b"\x00\x06HEADER")
    directory.joinpath(f"{stem}.tech").write_text("layer D0_TOP_M1\n", encoding="utf-8")
    directory.joinpath(f"{stem}.xml").write_text("<Control />\n", encoding="utf-8")
    directory.joinpath(f"{stem}_layer_mapping.json").write_text(
        json.dumps(
            {
                "artifact_stem": stem,
                "units": "um",
                "layers": [
                    {
                        "layer_name": "D0_TOP_M1",
                        "aedt_import_policy": "gds_import",
                        "aedt_layer_number": 1,
                        "aedt_datatype": 0,
                        "aedt_layer_tuple": "1/0",
                        "aedt_object_name_base": "D0_TOP_M1",
                        "material": "Al",
                        "recommended_aedt_role": "conductor",
                        "zmin_um": 0.0,
                        "thickness_um": 0.2,
                        "bbox_ymin_um": -100.0,
                        "bbox_ymax_um": 100.0,
                    },
                    {
                        "layer_name": "D1_BOTTOM_M1",
                        "aedt_import_policy": "gds_import",
                        "aedt_layer_number": 3,
                        "aedt_datatype": 0,
                        "aedt_layer_tuple": "3/0",
                        "aedt_object_name_base": "D1_BOTTOM_M1",
                        "material": "Al",
                        "recommended_aedt_role": "conductor",
                        "zmin_um": 7.7,
                        "thickness_um": 0.2,
                        "bbox_ymin_um": -100.0,
                        "bbox_ymax_um": 100.0,
                    },
                    {
                        "layer_name": "D0_SUBSTRATE",
                        "aedt_import_policy": "region",
                        "aedt_layer_number": 2,
                        "aedt_datatype": 0,
                        "aedt_layer_tuple": "2/0",
                        "aedt_object_name_base": "D0_SUBSTRATE",
                        "material": "Si",
                        "recommended_aedt_role": "dielectric_volume",
                        "zmin_um": -500.0,
                        "thickness_um": 500.0,
                        "bbox_ymin_um": -100.0,
                        "bbox_ymax_um": 100.0,
                    },
                    {
                        "layer_name": "D1_SUBSTRATE",
                        "aedt_import_policy": "region",
                        "aedt_layer_number": 4,
                        "aedt_datatype": 0,
                        "aedt_layer_tuple": "4/0",
                        "aedt_object_name_base": "D1_SUBSTRATE",
                        "material": "Si",
                        "recommended_aedt_role": "dielectric_volume",
                        "zmin_um": 7.9,
                        "thickness_um": 500.0,
                        "bbox_ymin_um": -100.0,
                        "bbox_ymax_um": 100.0,
                    },
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    directory.joinpath(f"{stem}_cross_section.json").write_text(
        json.dumps(
            {
                "point_slug": stem,
                "case_kind": "public_two_trace_flip_chip",
                "parameters": {
                    "case_kind": "public_two_trace_flip_chip",
                    "cpw_left_gap_um": 6.0,
                    "cpw_width_um": 10.0,
                    "cpw_right_gap_um": 6.0,
                    "flip_chip_gap_um": 7.5,
                    "horizontal_offset_um": 10.0,
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    directory.joinpath(f"{stem}_q2d_conductors.json").write_text(
        json.dumps(
            {
                "conductors": [
                    {
                        "name": "q2d_d0_signal",
                        "center_y_um": 0.0,
                        "layer_stack_layer_name": "D0_TOP_M1",
                        "conductor_type": "Signal Line",
                        "assignment_name": "Trace1",
                    },
                    {
                        "name": "q2d_d0_left_ground",
                        "center_y_um": -16.0,
                        "layer_stack_layer_name": "D0_TOP_M1",
                        "conductor_type": "Reference Ground",
                        "assignment_name": "Ground",
                    },
                    {
                        "name": "q2d_d0_right_ground",
                        "center_y_um": 16.0,
                        "layer_stack_layer_name": "D0_TOP_M1",
                        "conductor_type": "Reference Ground",
                        "assignment_name": "Ground",
                    },
                    {
                        "name": "q2d_d1_signal",
                        "center_y_um": 10.0,
                        "layer_stack_layer_name": "D1_BOTTOM_M1",
                        "conductor_type": "Signal Line",
                        "assignment_name": "Trace2",
                    },
                    {
                        "name": "q2d_d1_left_ground",
                        "center_y_um": -6.0,
                        "layer_stack_layer_name": "D1_BOTTOM_M1",
                        "conductor_type": "Reference Ground",
                        "assignment_name": "Ground",
                    },
                    {
                        "name": "q2d_d1_right_ground",
                        "center_y_um": 26.0,
                        "layer_stack_layer_name": "D1_BOTTOM_M1",
                        "conductor_type": "Reference Ground",
                        "assignment_name": "Ground",
                    },
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )
