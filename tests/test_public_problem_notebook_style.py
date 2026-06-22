"""Policy tests for publication-safe OrPen notebook source files."""

from __future__ import annotations

import ast
from pathlib import Path

NOTEBOOK_SOURCE_DIR = Path("notebooks/src")
HANDOFF_NOTEBOOKS = (
    NOTEBOOK_SOURCE_DIR / "public_driven_workflow.py",
    NOTEBOOK_SOURCE_DIR / "public_eigenmode_workflow.py",
    NOTEBOOK_SOURCE_DIR / "public_electrostatic_workflow.py",
    NOTEBOOK_SOURCE_DIR / "public_surface_epr_ribbon_capacitor_workflow.py",
)
LOCAL_NOTEBOOKS = (
    NOTEBOOK_SOURCE_DIR / "public_driven_local_workflow.py",
    NOTEBOOK_SOURCE_DIR / "public_eigenmode_local_workflow.py",
    NOTEBOOK_SOURCE_DIR / "public_electrostatic_local_workflow.py",
    NOTEBOOK_SOURCE_DIR / "public_surface_epr_ribbon_capacitor_local_workflow.py",
    NOTEBOOK_SOURCE_DIR / "public_purcell_driven_local_workflow.py",
    NOTEBOOK_SOURCE_DIR / "public_purcell_eigenmode_local_workflow.py",
)
PROBLEM_NOTEBOOKS = HANDOFF_NOTEBOOKS + LOCAL_NOTEBOOKS
GENERATED_NOTEBOOK_DIRS = (Path("notebooks"), Path("docs/notebooks"))
PURCELL_LOCAL_NOTEBOOKS = (
    NOTEBOOK_SOURCE_DIR / "public_purcell_driven_local_workflow.py",
    NOTEBOOK_SOURCE_DIR / "public_purcell_eigenmode_local_workflow.py",
)
SURFACE_EPR_NOTEBOOK = (
    NOTEBOOK_SOURCE_DIR / "public_surface_epr_ribbon_capacitor_workflow.py"
)
SURFACE_EPR_LOCAL_NOTEBOOK = (
    NOTEBOOK_SOURCE_DIR / "public_surface_epr_ribbon_capacitor_local_workflow.py"
)


def _is_private_name(name: str) -> bool:
    return any(part.startswith("_") and not part.startswith("__") for part in name.split("."))


def _method_calls(tree: ast.AST, method_name: str) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == method_name
    ]


def _keyword_names(call: ast.Call) -> set[str]:
    return {keyword.arg for keyword in call.keywords if keyword.arg is not None}


def test_public_problem_type_notebooks_are_split() -> None:
    assert not (NOTEBOOK_SOURCE_DIR / "public_simulation_workflows.py").exists()
    for notebook in PROBLEM_NOTEBOOKS:
        assert notebook.exists()


def test_public_notebook_sources_exist() -> None:
    for notebook in PROBLEM_NOTEBOOKS:
        assert notebook.exists()


def test_public_problem_notebooks_are_not_executed_by_default_docs_build() -> None:
    conf = Path("docs/conf.py").read_text()
    assert "nb_execution_excludepatterns" in conf
    assert '"notebooks/public_*_workflow.ipynb"' in conf


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


def test_public_notebooks_use_pdk_stack_with_explicit_region_activation() -> None:
    for notebook in PROBLEM_NOTEBOOKS:
        source = notebook.read_text()
        assert "sim.set_stack(PDK.get_layer_stack())" in source
        assert "include_substrate=True" not in source
        assert ".set_airbox(" not in source

    for notebook in PROBLEM_NOTEBOOKS:
        source = notebook.read_text()
        assert 'sim.activate_substrate(\n        layer="D0_SUBSTRATE",' in source
        assert 'die="D0"' in source
        assert "margin_x=500.0" in source
        assert "margin_y=500.0" in source
        assert "sim.activate_outer_vacuum(" in source
        assert "margin_x=0.0" in source
        assert "margin_y=0.0" in source
        assert "z_above=" in source
        assert "z_below=" in source
        assert "D1_SUBSTRATE" not in source
        assert "activate_inter_die_vacuum(" not in source


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
        assert not called_names & old_report_display_names


def test_public_problem_notebooks_show_versioned_palace_config_controls() -> None:
    for notebook in PROBLEM_NOTEBOOKS:
        source = notebook.read_text()
        tree = ast.parse(source, filename=str(notebook))
        assert 'PALACE_CONFIG_VERSION = "0.16.0"' not in source
        assert "PalaceRefinementConfig" not in source
        assert "PalaceLinearSolverConfig" not in source

        refinement_calls = _method_calls(tree, "set_refinement")
        linear_solver_calls = _method_calls(tree, "set_linear_solver")
        output_format_calls = _method_calls(tree, "set_output_formats")
        assert len(refinement_calls) == 1
        assert len(linear_solver_calls) == 1
        assert len(output_format_calls) == 1
        assert refinement_calls[0].args == []
        assert linear_solver_calls[0].args == []
        assert output_format_calls[0].args == []
        refinement_keywords = {
            keyword.arg: keyword.value
            for keyword in refinement_calls[0].keywords
            if keyword.arg is not None
        }
        assert {"max_its", "tol", "update_fraction"} <= set(refinement_keywords)
        assert ast.literal_eval(refinement_keywords["max_its"]) == 15
        assert ast.literal_eval(refinement_keywords["tol"]) == 1e-3
        assert ast.literal_eval(refinement_keywords["update_fraction"]) == 0.3
        assert {"tol", "max_its", "estimator_mg"} <= _keyword_names(linear_solver_calls[0])
        assert {"paraview", "grid_function"} <= _keyword_names(output_format_calls[0])
        assert "uniform_levels=" not in source
        assert "max_its=6" not in source
        assert "max_its=2000" in source
        assert "grid_function=False" in source
        assert 'type="AMS"' not in source
        assert "ams_max_its=" not in source
        assert 'sim.set_palace_version("0.16.0")' in source
        assert "validate_schema=True" in source


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
        assert "NOTEBOOK_REQUIRE_REPORT" not in source
        assert "if NOTEBOOK_PREPARE_RUN_STAGE:\n    NOTEBOOK_RUN_ROOT.mkdir" in source
        assert "shutil.rmtree" not in source
        assert '"mesh-config"' not in source


def test_public_problem_notebooks_configure_public_hpc_handoff_in_run_cell() -> None:
    for notebook in HANDOFF_NOTEBOOKS:
        source = notebook.read_text()
        tree = ast.parse(source, filename=str(notebook))
        simulation_imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and node.module == "orpen_sc_pdk.simulation"
            for alias in node.names
        }
        assert "resolve_public_palace_run_profile" in simulation_imports
        assert "from gsim.palace.handoff import PalaceSlurmSbatchSpec" not in source
        assert "write_palace_slurm_sbatch_handoff" not in source
        assert "PALACE_HPC_PROFILE =" in source
        assert "PALACE_HPC_RESOURCE_OVERRIDES =" in source
        assert "resolve_public_palace_run_profile(" in source
        assert "run_profile.to_palace_config_hints()" in source
        assert "sim.write_slurm_sbatch_handoff(" in source
        assert "write_config=False" in source
        assert "script_path=sbatch_handoff.script_path" in source
        assert "sim.generate_handoff_package(" in source
        assert "globals()" not in source
        assert "ORPEN_RUN_LOCAL_PALACE_SMOKE" not in source
        assert "profile_setup_commands = run_profile.launcher.setup_commands" not in source
        assert "setup_commands=direct_setup_commands" not in source


def test_public_local_notebooks_configure_run_local_in_run_cell() -> None:
    for notebook in LOCAL_NOTEBOOKS:
        source = notebook.read_text()
        assert "from orpen_sc_pdk.simulation import resolve_public_palace_run_profile" not in source
        assert "# ## Run Stage (run_local)" in source
        assert "PALACE_RUN_LOCAL = False" in source
        assert "PALACE_SETUP_COMMANDS = ('eval \"$(spack load --sh palace)\"',)" in source
        assert "PALACE_EXECUTABLE_MODE =" in source
        assert "sim.run_local(**local_run_kwargs)" in source
        assert "setup_commands" in source
        assert "generate_handoff_package" not in source
        assert "write_slurm_sbatch_handoff" not in source
        assert "PALACE_HPC_PROFILE" not in source
        assert "run_handle.run_folder" not in source
        assert "globals()" not in source


def test_public_purcell_notebooks_only_add_readout_lumped_ports() -> None:
    expected_ports = {"o_lumped_readout_in", "o_lumped_readout_out"}
    mesh_marker_ports = {
        "o_mesh_readout_in",
        "o_mesh_readout_out",
        "o_mesh_purcell_filter",
    }
    for notebook in PURCELL_LOCAL_NOTEBOOKS:
        source = notebook.read_text()
        tree = ast.parse(source, filename=str(notebook))
        add_port_calls = {
            call.args[0].value: call
            for call in ast.walk(tree)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "add_port"
            and call.args
            and isinstance(call.args[0], ast.Constant)
            and isinstance(call.args[0].value, str)
        }
        assert set(add_port_calls) == expected_ports
        assert set(add_port_calls).isdisjoint(mesh_marker_ports)
        excited_by_port = {
            name: next(
                (
                    keyword.value.value
                    for keyword in call.keywords
                    if keyword.arg == "excited"
                    and isinstance(keyword.value, ast.Constant)
                ),
                True,
            )
            for name, call in add_port_calls.items()
        }
        if notebook.name == "public_purcell_driven_local_workflow.py":
            assert excited_by_port == {
                "o_lumped_readout_in": True,
                "o_lumped_readout_out": False,
            }
        else:
            assert excited_by_port == {
                "o_lumped_readout_in": False,
                "o_lumped_readout_out": False,
            }
        assert "global_purcell_filter_demo_chip" in source
        assert "get_gsim_palace_simulation_layer_catalog" in source
        assert "sim.set_simulation_layers(" in source
        assert "generate_sheet=False" in source
        assert "port_sheet_physical_names" in source
        assert '"layout-authored"' in source


def test_public_surface_epr_notebook_teaches_route_b_ribbon_capacitor_groups() -> None:
    source = SURFACE_EPR_NOTEBOOK.read_text()
    tree = ast.parse(source, filename=str(SURFACE_EPR_NOTEBOOK))
    assignments = {
        target.id: node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }

    assert "martinis2022_differential_ribbon_capacitor" in source
    assert "ell_r_um=MARTINIS_NOTEBOOK_LENGTH_UM,\n    ).copy()" in source
    assert "MARTINIS_RIBBON_A_UM = 50.0" in source
    assert "MARTINIS_RIBBON_B_UM = 100.0" in source
    assert "MARTINIS_NOTEBOOK_LENGTH_UM = 1391.0" in source
    assert "DOI: 10.1038/s41534-022-00530-6" in source
    assert "get_gsim_palace_simulation_layer_catalog" not in source
    assert "get_gsim_palace_surface_epr_layer_number" not in source
    assert "add_source_surface_epr_regions(" not in source
    assert "build_source_surface_epr_dielectric_specs_from_interfaces(" not in source
    assert "build_interface_surface_catalog(mesh_result.groups)" in source
    assert "build_surface_epr_dielectric_specs(" in source
    assert "build_dielectric_interface_specs_from_material_kinds(" not in source
    assert "surface_epr_catalog" in source
    assert "sim.set_simulation_layers(surface_epr_catalog)" not in source
    assert ast.literal_eval(assignments["SURFACE_EPR_INSET_NM"]) == 50
    assert ast.literal_eval(assignments["SURFACE_EPR_INSET_MARGINS_NM"]) == (
        0,
        50,
        100,
        200,
        500,
        1000,
    )
    assert "SURFACE_EPR_CUTOFFS_WITH_EDGE_UM" not in source
    assert "SURFACE_EPR_SOURCE_SHEETS" not in source
    assert "finite_shell_route_b" in source
    assert "inset partitioning" in source
    assert "surface_epr_margin_groups" not in source
    assert "surface_epr_core_groups" not in source
    assert "source_aware_surface_epr_groups =" not in source
    assert "surface_epr_group_rows" not in source
    assert "total_source_aware_groups" not in source
    assert "surface_epr_dielectric_specs" in source
    assert "dielectric_interfaces=surface_epr_dielectric_specs" in source
    assert "surface_epr_ms_bottom_entries" in source
    assert "D0_TOP_M1_pec_0" not in source
    assert "D0_TOP_M1_pec_1" not in source
    assert "region.name" not in source
    assert "region.kind" not in source
    assert "add_surface_epr_bands(" not in source
    assert "D0_TOP_SURFACE_EPR_BAND" not in source
    assert "d0_top_surface_epr" not in source
    assert '"interface_type": "MS"' in source
    assert '"interface_type": "MA"' not in source
    assert '"interface_type": "SA"' not in source
    assert "SURFACE_EPR_ACTIVE_INTERFACE_PRESET_NAMES = (\"martinis2022_ms\",)" in source
    assert "preset=surface_epr_ms" in source
    assert "substrate_air_surface_epr_specs" not in source
    assert '"active_loss_channels": ("MS",)' in source
    assert "SURFACE_EPR_POSTPROCESSING_STATUS" not in source
    assert "TODO: consume the corrected gsim Surface EPR API here" not in source
    assert "paper_reference_capacitance_ff" in source


def test_public_surface_epr_local_notebook_uses_route_b_postprocessing() -> None:
    source = SURFACE_EPR_LOCAL_NOTEBOOK.read_text()

    assert "add_source_surface_epr_regions(" not in source
    assert "build_source_surface_epr_dielectric_specs_from_interfaces(" not in source
    assert "build_source_surface_epr_shell_dielectric_specs(" not in source
    assert "build_interface_surface_catalog(mesh_result.groups)" in source
    assert "build_surface_epr_dielectric_specs(" in source
    assert "build_dielectric_interface_specs_from_material_kinds(" not in source
    assert "get_gsim_palace_surface_epr_layer_number" not in source
    assert "surface_epr_catalog" in source
    assert "sim.set_simulation_layers(surface_epr_catalog)" not in source
    assert "dielectric_interfaces=surface_epr_dielectric_specs" in source
    assert "SURFACE_EPR_USE_FINITE_METAL_SHELL = True" in source
    assert "planar_conductors=SURFACE_EPR_PLANAR_CONDUCTORS" in source
    assert "surface_epr_inset_margins_um=SURFACE_EPR_INSET_MARGINS_UM" in source
    assert '"surface_epr_ms_bottom_entries"' in source
    assert '"mesh_manifest_surface_epr_entries"' in source
    assert "substrate_air_surface_epr_specs" not in source
    assert '"active_loss_channels": ("MS",)' in source
    assert "SURFACE_EPR_POSTPROCESSING_STATUS" not in source
    assert "TODO: consume the corrected gsim Surface EPR API here" not in source
    assert "# ## Run Stage (run_local)" in source
    assert "PALACE_RUN_LOCAL = False" in source
    assert "sim.run_local(**local_run_kwargs)" in source
    assert "resolve_public_palace_run_profile" not in source
    assert "sim.write_slurm_sbatch_handoff(" not in source
    assert "sim.generate_handoff_package(" not in source


def test_public_problem_notebooks_do_not_write_synthetic_report_fixtures() -> None:
    for notebook in PROBLEM_NOTEBOOKS:
        source = notebook.read_text()
        assert "Docs-safe report fixture" not in source
        assert "report-fixture" not in source
        assert 'NOTEBOOK_RUN_ROOT / "results" / "report"' not in source
        assert "analysis_run_root = Path(NOTEBOOK_ANALYSIS_RUN_ROOT or NOTEBOOK_RUN_ROOT)" in source
        assert "load_report(require_report=True).require_report()" in source
        assert "report_bundle" not in source
        assert "run_stage_summary" not in source
        assert "missing_artifacts" not in source
        assert "mesh_path" not in source


def test_public_problem_notebooks_use_typed_visualization_outputs() -> None:
    for notebook in PROBLEM_NOTEBOOKS:
        source = notebook.read_text()
        assert ".show_all_results()" in source
        assert "loss_budget_bar_plot" not in source


def test_generated_public_problem_notebooks_follow_source_policy_when_present() -> None:
    banned_text = (
        "import orpen_sc_pdk",
        "from orpen_sc_pdk import",
        "orpen_sc_pdk.activate()",
        "PalaceLinearSolverConfig",
        "PalaceRefinementConfig",
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
