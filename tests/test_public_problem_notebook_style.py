"""Policy tests for publication-safe OrPen notebook source files."""

from __future__ import annotations

import ast
from pathlib import Path

NOTEBOOK_SOURCE_DIR = Path("notebooks/src")
HANDOFF_NOTEBOOKS = (
    NOTEBOOK_SOURCE_DIR / "public_driven_workflow.py",
    NOTEBOOK_SOURCE_DIR / "public_eigenmode_workflow.py",
    NOTEBOOK_SOURCE_DIR / "public_electrostatic_workflow.py",
)
LOCAL_NOTEBOOKS = (
    NOTEBOOK_SOURCE_DIR / "public_driven_local_workflow.py",
    NOTEBOOK_SOURCE_DIR / "public_eigenmode_local_workflow.py",
    NOTEBOOK_SOURCE_DIR / "public_electrostatic_local_workflow.py",
)
PROBLEM_NOTEBOOKS = HANDOFF_NOTEBOOKS + LOCAL_NOTEBOOKS
GENERATED_NOTEBOOK_DIRS = (Path("notebooks"), Path("docs/notebooks"))


def _is_private_name(name: str) -> bool:
    return any(part.startswith("_") and not part.startswith("__") for part in name.split("."))


def test_public_problem_type_notebooks_are_split() -> None:
    assert not (NOTEBOOK_SOURCE_DIR / "public_simulation_workflows.py").exists()
    for notebook in PROBLEM_NOTEBOOKS:
        assert notebook.exists()


def test_public_notebook_sources_exist() -> None:
    for notebook in PROBLEM_NOTEBOOKS:
        assert notebook.exists()


def test_public_notebook_index_does_not_link_combined_simulation_workflow() -> None:
    assert "public_simulation_workflows" not in Path("docs/notebooks.rst").read_text()


def test_public_notebooks_do_not_define_local_functions() -> None:
    for notebook in PROBLEM_NOTEBOOKS:
        tree = ast.parse(notebook.read_text(), filename=str(notebook))
        definitions = [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        ]
        assert definitions == []


def test_public_notebooks_do_not_reference_private_symbols() -> None:
    for notebook in PROBLEM_NOTEBOOKS:
        tree = ast.parse(notebook.read_text(), filename=str(notebook))
        private_symbols = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                private_symbols.extend(
                    alias.asname or alias.name
                    for alias in node.names
                    if _is_private_name(alias.name)
                    or (alias.asname is not None and _is_private_name(alias.asname))
                )
            elif isinstance(node, ast.ImportFrom):
                private_symbols.extend(
                    alias.asname or alias.name
                    for alias in node.names
                    if _is_private_name(alias.name)
                    or (alias.asname is not None and _is_private_name(alias.asname))
                )
            elif isinstance(node, ast.Name) and _is_private_name(node.id):
                private_symbols.append(node.id)
            elif isinstance(node, ast.Attribute) and _is_private_name(node.attr):
                private_symbols.append(node.attr)
        assert private_symbols == []


def test_public_notebooks_do_not_use_root_pdk_import_or_activation() -> None:
    for notebook in PROBLEM_NOTEBOOKS:
        source = notebook.read_text()
        tree = ast.parse(source, filename=str(notebook))
        root_imports = [
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
            if alias.name == "orpen_sc_pdk"
        ]
        root_from_imports = [
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module == "orpen_sc_pdk"
        ]
        assert root_imports == []
        assert root_from_imports == []
        assert "orpen_sc_pdk.activate()" not in source


def test_public_pdk_notebooks_use_explicit_pdk_activation() -> None:
    for notebook in PROBLEM_NOTEBOOKS:
        source = notebook.read_text()
        assert "from orpen_sc_pdk.pdk import PDK" in source
        assert "PDK.activate()" in source


def test_public_problem_notebooks_do_not_hide_workflow_in_scripts() -> None:
    for notebook in PROBLEM_NOTEBOOKS:
        source = notebook.read_text()
        tree = ast.parse(source, filename=str(notebook))
        script_imports = [
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and node.module is not None
            and node.module.startswith("scripts")
        ]
        assert script_imports == []
        assert "tempfile" not in source
        assert "TemporaryDirectory" not in source


def test_public_problem_notebooks_show_gsim_workflow_chain() -> None:
    old_report_display_names = {
        "build_report_view",
        "display_report",
        "load_driven_report",
        "load_eigenmode_report",
        "load_electrostatic_report",
        "load_domain_material_summary",
        "load_dielectric_interface_summary",
        "load_result_view",
    }
    for notebook in PROBLEM_NOTEBOOKS:
        source = notebook.read_text()
        tree = ast.parse(source, filename=str(notebook))
        called_names = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        called_attributes = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        assert "set_geometry" in called_attributes
        assert "set_stack" in called_attributes
        assert "mesh" in called_attributes
        assert "write_config" in called_attributes
        assert "resolve_palace_result" in called_names
        assert "load_report" in called_attributes
        assert "require_report" in called_attributes
        assert "show_all_results" in called_attributes
        assert "visualize" in called_attributes
        assert not called_names & old_report_display_names


def test_public_problem_notebooks_show_reviewable_main_chain_cells() -> None:
    expected_headings = [
        "# ## Geometry",
        "# ## LayerStack",
        "# ## Mesh",
        "# ## Config",
        "# ## Resolve",
        "# ## Visualize",
        "# ## Report",
    ]
    for notebook in PROBLEM_NOTEBOOKS:
        source = notebook.read_text()
        run_heading = (
            "# ## Run Stage (run_local)"
            if notebook in LOCAL_NOTEBOOKS
            else "# ## Run Stage (handoff package)"
        )
        headings = expected_headings[:4] + [run_heading] + expected_headings[4:]
        positions = [source.index(heading) for heading in headings]
        assert positions == sorted(positions)


def test_public_problem_notebooks_use_explicit_date_index_run_folders() -> None:
    for notebook in PROBLEM_NOTEBOOKS:
        source = notebook.read_text()
        assert "from orpen_sc_pdk.config import PATH" in source
        assert 'NOTEBOOK_ROOT = PATH.simulation / "notebooks"' in source
        assert "NOTEBOOK_RUN_DATE = date.today().isoformat()" in source
        assert "NOTEBOOK_RUN_INDEX =" in source
        assert 'NOTEBOOK_RUN_ID = f"{NOTEBOOK_RUN_DATE}-Run{NOTEBOOK_RUN_INDEX:02d}"' in source
        assert "NOTEBOOK_RUN_ROOT = NOTEBOOK_ROOT / NOTEBOOK_RUN_ID" in source
        assert "NOTEBOOK_ANALYSIS_RUN_ROOT: Path | None = None" in source
        assert "NOTEBOOK_PREPARE_RUN_STAGE = NOTEBOOK_ANALYSIS_RUN_ROOT is None" in source
        assert "NOTEBOOK_REQUIRE_REPORT = False" in source
        assert "if NOTEBOOK_PREPARE_RUN_STAGE:\n    NOTEBOOK_RUN_ROOT.mkdir" in source
        assert "shutil.rmtree" not in source
        assert '"mesh-config"' not in source


def test_public_problem_notebooks_configure_public_hpc_handoff_in_run_cell() -> None:
    for notebook in HANDOFF_NOTEBOOKS:
        source = notebook.read_text()
        assert "from orpen_sc_pdk.simulation import resolve_public_palace_run_profile" in source
        assert "from gsim.palace.handoff import PalaceSlurmSbatchSpec" not in source
        assert "write_palace_slurm_sbatch_handoff" not in source
        assert "PALACE_HPC_PROFILE =" in source
        assert "PALACE_HPC_RESOURCE_OVERRIDES =" in source
        assert "resolve_public_palace_run_profile(" in source
        assert "run_profile.to_palace_config_hints()" in source
        assert "sim.write_slurm_sbatch_handoff(" in source
        assert "write_config=False" in source
        assert "script_path=sbatch_handoff.script_path" in source
        assert "run_handle.run_folder" in source
        assert 'if "run_handle" not in globals():' in source
        assert "ORPEN_RUN_LOCAL_PALACE_SMOKE" not in source
        assert "profile_setup_commands = run_profile.launcher.setup_commands" not in source
        assert "setup_commands=direct_setup_commands" not in source


def test_public_local_notebooks_configure_run_local_in_run_cell() -> None:
    for notebook in LOCAL_NOTEBOOKS:
        source = notebook.read_text()
        assert "from orpen_sc_pdk.simulation import resolve_public_palace_run_profile" not in source
        assert "# ## Run Stage (run_local)" in source
        assert "PALACE_RUN_LOCAL = False" in source
        assert 'PALACE_SETUP_COMMANDS = ("spack load palace",)' in source
        assert "PALACE_EXECUTABLE_MODE =" in source
        assert "local_results = sim.run_local(**local_run_kwargs)" in source
        assert "setup_commands" in source
        assert "generate_handoff_package" not in source
        assert "write_slurm_sbatch_handoff" not in source
        assert "PALACE_HPC_PROFILE" not in source
        assert "run_handle.run_folder" not in source
        assert 'if "output_dir" not in globals():' in source


def test_public_problem_notebooks_do_not_write_synthetic_report_fixtures() -> None:
    for notebook in PROBLEM_NOTEBOOKS:
        source = notebook.read_text()
        assert "Docs-safe report fixture" not in source
        assert "report-fixture" not in source
        assert 'NOTEBOOK_RUN_ROOT / "results" / "report"' not in source
        assert "analysis_run_root = NOTEBOOK_ANALYSIS_RUN_ROOT" in source
        assert "report_bundle = resolved_result.load_report(" in source


def test_generated_public_problem_notebooks_follow_source_policy_when_present() -> None:
    banned_text = (
        "import orpen_sc_pdk",
        "from orpen_sc_pdk import",
        "orpen_sc_pdk.activate()",
        "from scripts.",
        "tempfile",
        "TemporaryDirectory",
        "Docs-safe report fixture",
        "report-fixture",
        "Optional local Palace smoke",
        "ORPEN_RUN_LOCAL_PALACE_SMOKE",
    )
    for generated_dir in GENERATED_NOTEBOOK_DIRS:
        for source_notebook in PROBLEM_NOTEBOOKS:
            generated = generated_dir / source_notebook.with_suffix(".ipynb").name
            if not generated.exists():
                continue
            text = generated.read_text()
            offenders = [literal for literal in banned_text if literal in text]
            assert offenders == []
