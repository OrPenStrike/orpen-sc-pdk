"""Native masked Surface EPR notebook contract checks.

Responsibility:
Owns the OrPen notebook contract for reproducing the Martinis 2022 ribbon
native masked Surface EPR handoff with a Palace fork. The tests verify the
notebook keeps private paths out of source, validates a base `gsim` config
before applying the native Mask patch, and packages the patched config without
rewriting it.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

SOURCE = Path(
    "notebooks/src/Native_Masked_Surface_EPR/martinis2022_ribbon_native_mask_hpc_handoff.py"
)
NOTEBOOK = Path(
    "notebooks/Native_Masked_Surface_EPR/martinis2022_ribbon_native_mask_hpc_handoff.ipynb"
)
SGB_HELPER = Path(
    "notebooks/src/Native_Masked_Surface_EPR/sgb_native_mask_handoff_common.py"
)
SGB_ROUTE_SOURCES = {
    "A": Path(
        "notebooks/src/Native_Masked_Surface_EPR/"
        "martinis2022_ribbon_sgb_route_a_native_mask_hpc_handoff.py"
    ),
    "B": Path(
        "notebooks/src/Native_Masked_Surface_EPR/"
        "martinis2022_ribbon_sgb_route_b_native_mask_hpc_handoff.py"
    ),
}
SGB_ROUTE_NOTEBOOKS = {
    "A": Path(
        "notebooks/Native_Masked_Surface_EPR/"
        "martinis2022_ribbon_sgb_route_a_native_mask_hpc_handoff.ipynb"
    ),
    "B": Path(
        "notebooks/Native_Masked_Surface_EPR/"
        "martinis2022_ribbon_sgb_route_b_native_mask_hpc_handoff.ipynb"
    ),
}
PURE_ANALYSIS_SOURCE = Path(
    "notebooks/src/Native_Masked_Surface_EPR/native_mask_surface_epr_analysis.py"
)
PURE_ANALYSIS_NOTEBOOK = Path(
    "notebooks/Native_Masked_Surface_EPR/native_mask_surface_epr_analysis.ipynb"
)
ROUTE_B_ANALYSIS_NOTEBOOK = Path(
    "build/simulation/notebooks/Native_Masked_Surface_EPR/"
    "martinis2022_ribbon_sgb_route_b_native_mask_hpc_handoff/"
    "2026-07-03-Run01/sgb_route_b_native_mask_surface_epr_analysis.ipynb"
)
DOC = Path("docs/features/native-masked-surface-epr-handoff.md")


def _assignments(path: Path) -> dict[str, ast.expr]:
    tree = ast.parse(path.read_text())
    return {
        target.id: node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }


def test_native_masked_surface_epr_files_exist() -> None:
    assert SOURCE.exists()
    assert NOTEBOOK.exists()
    assert SGB_HELPER.exists()
    assert all(path.exists() for path in SGB_ROUTE_SOURCES.values())
    assert all(path.exists() for path in SGB_ROUTE_NOTEBOOKS.values())
    assert PURE_ANALYSIS_SOURCE.exists()
    assert PURE_ANALYSIS_NOTEBOOK.exists()
    assert ROUTE_B_ANALYSIS_NOTEBOOK.exists()
    assert DOC.exists()


def test_native_masked_surface_epr_notebook_uses_public_orpen_geometry() -> None:
    source = SOURCE.read_text()
    assignments = _assignments(SOURCE)

    assert "martinis2022_differential_ribbon_capacitor" in source
    assert "from orpen_sc_pdk.cells import martinis2022_differential_ribbon_capacitor" in source
    assert "NCUAS_SC_Qubit_Design" not in source
    assert "/home/ili/" not in source
    assert ast.literal_eval(assignments["MARTINIS_RIBBON_A_UM"]) == 50.0
    assert ast.literal_eval(assignments["MARTINIS_RIBBON_B_UM"]) == 100.0
    assert ast.literal_eval(assignments["MARTINIS_NOTEBOOK_LENGTH_UM"]) == 1391.0
    assert "planar_conductors=True" in source


def test_native_masked_surface_epr_notebook_patches_legacy_run02_native_mask_rows() -> None:
    source = SOURCE.read_text()
    assignments = _assignments(SOURCE)

    assert ast.literal_eval(assignments["PALACE_ORDER"]) == 2
    assert ast.literal_eval(assignments["HPC_MAX_ITS"]) == 20
    assert ast.literal_eval(assignments["PALACE_UPDATE_FRACTION"]) == 0.15
    assert ast.literal_eval(assignments["NATIVE_MASK_MARGINS_L0_UNITS"]) == (
        0.0,
        0.01,
        0.05,
        0.1,
        0.2,
        0.5,
        1.0,
    )
    assert "LEGACY_RUN02_SUBSTRATE_PERMITTIVITY = 11.7" in source
    assert '"SA": {"thickness": 0.002, "permittivity": 3.8, "loss_tangent": 0.0017}' in source
    assert '"MS": {"thickness": 0.002, "permittivity": 9.8, "loss_tangent": 0.00048}' in source
    assert '"MA": {"thickness": 0.002, "permittivity": 9.8, "loss_tangent": 0.0033}' in source
    assert '"Mask": {"Type": "Inset", "Margin": margin_l0}' in source
    assert '"dielectric_postprocessing_rows": len(native_mask_dielectric_rows)' in source


def test_native_masked_surface_epr_notebook_does_not_let_packaging_rewrite_config() -> None:
    source = SOURCE.read_text()

    assert "validate_schema=True" in source
    assert 'config_path.write_text(json.dumps(palace_config, indent=2) + "\\n")' in source
    assert "native_mask_launcher = PalaceSlurmLauncherSpec(" in source
    assert "native_mask_profile_metadata =" in source
    assert "profile=native_mask_profile_metadata" in source
    assert "PALACE_NATIVE_MASK_BUNDLE_EXECUTABLE" in source
    assert 'PALACE_NATIVE_MASK_BUNDLE_EXECUTABLE", "1"' in source
    assert '"palace-x86_64.bin"' in source
    assert "shutil.copy2(source_executable, bundled_executable)" in source
    assert "sim.write_slurm_sbatch_handoff(" in source
    assert "palace_executable=PALACE_NATIVE_MASK_EXECUTABLE" in source
    assert "command_style=PALACE_NATIVE_MASK_COMMAND_STYLE" in source
    assert "setup_commands=PALACE_NATIVE_MASK_SETUP_COMMANDS" in source
    assert "sim.generate_handoff_package(" in source
    assert "write_config=False" in source


def test_native_masked_surface_epr_notebook_json_has_matching_source() -> None:
    payload = json.loads(NOTEBOOK.read_text())
    assert "jupytext" in payload["metadata"]
    joined_source = "".join("".join(cell.get("source", ())) for cell in payload["cells"])

    assert "Native Masked Surface EPR Convergence" in joined_source
    assert "native_mask_surface_epr_history.csv" in joined_source


def test_sgb_route_native_mask_helper_uses_route_geometry_sidecars_only() -> None:
    source = SGB_HELPER.read_text()
    assignments = _assignments(SGB_HELPER)
    tree = ast.parse(source)
    top_level_imports = [
        node
        for node in tree.body
        if isinstance(node, ast.Import | ast.ImportFrom)
    ]

    assert ast.literal_eval(assignments["PALACE_ORDER"]) == 2
    assert ast.literal_eval(assignments["HPC_MAX_ITS"]) == 20
    assert ast.literal_eval(assignments["NATIVE_MASK_MARGINS_NM"]) == (
        0,
        50,
        100,
        200,
        500,
        1000,
    )
    assert "sim.set_surface_epr(representation=route, interfaces=None)" in source
    assert "inset_margins_um" not in source
    assert "with_inset" not in source
    assert 'os.environ.get("PALACE_HPC_MEMORY_MB", "480000")' in source
    assert 'PALACE_NATIVE_MASK_BUNDLE_EXECUTABLE", "1"' in source
    assert '"palace-x86_64.bin"' in source
    assert '"Mask": {"Type": "Inset", "Margin": margin_l0}' in source
    assert '"surface_epr_interface_records": interface_records' in source
    assert "metadata/semantic_geometry/04_export_physical_groups.json" in source
    assert "sgb_route_{route.lower()}_physical_group_config_map.csv" in source
    assert "analysis_run_root: Path | None = None" in source
    assert "NOTEBOOK_ANALYSIS_RUN_ROOT" not in source
    assert not any(
        (
            isinstance(node, ast.ImportFrom)
            and node.module is not None
            and node.module.split(".", 1)[0] == "gsim"
        )
        or (
            isinstance(node, ast.Import)
            and any(alias.name.split(".", 1)[0] == "gsim" for alias in node.names)
        )
        for node in top_level_imports
    )


def test_sgb_route_native_mask_notebooks_select_one_route_each() -> None:
    for route, source_path in SGB_ROUTE_SOURCES.items():
        source = source_path.read_text()
        expected_call = (
            f'run_sgb_native_mask_handoff("{route}", '
            "analysis_run_root=ANALYSIS_RUN_ROOT)"
        )
        assert expected_call in source
        assert "ANALYSIS_RUN_ROOT: Path | None = None" in source
        assert "sgb_native_mask_handoff_common" in source
        assert "NCUAS_SC_Qubit_Design" not in source
        assert "/home/ili/" not in source


def test_sgb_route_native_mask_notebook_json_has_matching_source() -> None:
    for route, notebook_path in SGB_ROUTE_NOTEBOOKS.items():
        payload = json.loads(notebook_path.read_text())
        assert "jupytext" in payload["metadata"]
        joined_source = "".join("".join(cell.get("source", ())) for cell in payload["cells"])
        assert f"SGB Route {route} Native Mask" in joined_source
        expected_call = (
            f'run_sgb_native_mask_handoff("{route}", '
            "analysis_run_root=ANALYSIS_RUN_ROOT)"
        )
        assert expected_call in joined_source


def test_native_mask_surface_epr_pure_analysis_notebook_contract() -> None:
    source = PURE_ANALYSIS_SOURCE.read_text()
    tree = ast.parse(source)
    top_level_imports = [
        node
        for node in tree.body
        if isinstance(node, ast.Import | ast.ImportFrom)
    ]
    assert not any(
        (
            isinstance(node, ast.ImportFrom)
            and node.module is not None
            and node.module.split(".", 1)[0] == "gsim"
        )
        or (
            isinstance(node, ast.Import)
            and any(alias.name.split(".", 1)[0] == "gsim" for alias in node.names)
        )
        for node in top_level_imports
    )
    assert "RUN_ROOT: Path = Path(" in source
    assert source.index("PASS_INDEX = 18") > source.index("# ## Adaptive Pass Summary")

    payload = json.loads(PURE_ANALYSIS_NOTEBOOK.read_text())
    route_b_payload = json.loads(ROUTE_B_ANALYSIS_NOTEBOOK.read_text())
    for notebook_payload in (payload, route_b_payload):
        for cell in notebook_payload["cells"]:
            if cell.get("cell_type") == "markdown":
                assert "execution_count" not in cell
                assert "outputs" not in cell

    headings = [
        "".join(cell.get("source", ())).strip()
        for cell in payload["cells"]
        if cell.get("cell_type") == "markdown"
    ]
    assert headings == [
        "# Native Masked Surface EPR Analysis",
        "## Convergence Plots",
        "## Adaptive Pass Summary",
        "## Last Summary",
    ]
    joined_source = "".join("".join(cell.get("source", ())) for cell in payload["cells"])
    assert "from gsim" not in joined_source
    assert "import gsim" not in joined_source

    route_b_source = "".join(
        "".join(cell.get("source", ())) for cell in route_b_payload["cells"]
    )
    assert "martinis2022_ribbon_sgb_route_b_native_mask_hpc_handoff/2026-07-03-Run01" in (
        route_b_source
    )
    assert "PASS_INDEX = 16" in route_b_source
