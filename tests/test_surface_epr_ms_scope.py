"""Surface EPR notebook scope tests.

Responsibility:
Owns the public notebook contract for Surface EPR public preset scope and Route
C mesh-interface evidence.
Does not own broader MA/SA loss-preset policy or Palace report parsing.
Source of Truth: docs/notebooks.rst and docs/developing-features.md.
"""

from __future__ import annotations

import ast
from pathlib import Path

NOTEBOOK_SOURCE_DIR = Path("notebooks/src")
SURFACE_EPR_MS_ONLY_NOTEBOOK_REPRESENTATIONS = {
    Path("notebooks/src/public_surface_epr_ribbon_capacitor_representation_a_workflow.py"): "A",
}
SURFACE_EPR_B_HANDOFF_NOTEBOOK = Path(
    "notebooks/src/public_surface_epr_ribbon_capacitor_workflow.py"
)
SURFACE_EPR_B_LOCAL_NOTEBOOK = Path(
    "notebooks/src/public_surface_epr_ribbon_capacitor_representation_b_local_workflow.py"
)
SURFACE_EPR_C_NOTEBOOK = Path(
    "notebooks/src/public_surface_epr_ribbon_capacitor_representation_c_workflow.py"
)


def _assignments(source: str) -> dict[str, ast.expr]:
    tree = ast.parse(source)
    return {
        target.id: node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }


def _literal_or_assigned_value(assignments: dict[str, ast.expr], expression: ast.expr) -> object:
    if isinstance(expression, ast.Constant):
        return expression.value
    if isinstance(expression, ast.Name) and expression.id in assignments:
        return ast.literal_eval(assignments[expression.id])
    return None


def _surface_epr_representations(source: str) -> tuple[object, ...]:
    tree = ast.parse(source)
    assignments = _assignments(source)
    return tuple(
        _literal_or_assigned_value(assignments, keyword.value)
        for call in ast.walk(tree)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and call.func.attr == "set_surface_epr"
        for keyword in call.keywords
        if keyword.arg == "representation"
    )


def _planar_conductors_keyword_values(source: str) -> tuple[object, ...]:
    tree = ast.parse(source)
    assignments = _assignments(source)
    return tuple(
        _literal_or_assigned_value(assignments, keyword.value)
        for call in ast.walk(tree)
        if isinstance(call, ast.Call)
        for keyword in call.keywords
        if keyword.arg == "planar_conductors"
    )


def test_surface_epr_route_notebooks_use_full_3d_reference_topology() -> None:
    checked_notebooks = []

    for notebook in sorted(NOTEBOOK_SOURCE_DIR.rglob("*.py")):
        source = notebook.read_text()
        representations = {
            representation
            for representation in _surface_epr_representations(source)
            if representation in {"A", "B", "C"}
        }
        if not representations:
            continue

        checked_notebooks.append(notebook)
        planar_conductors_values = _planar_conductors_keyword_values(source)

        assert "SURFACE_EPR_USE_FINITE_METAL_SHELL" not in source
        assert "planar_conductors=True" not in source
        assert planar_conductors_values
        assert all(value is False for value in planar_conductors_values), (
            notebook,
            planar_conductors_values,
        )

    assert checked_notebooks


def test_surface_epr_a_notebook_is_ms_only() -> None:
    for notebook, representation in SURFACE_EPR_MS_ONLY_NOTEBOOK_REPRESENTATIONS.items():
        source = notebook.read_text()
        assignments = _assignments(source)

        assert ast.literal_eval(assignments["SURFACE_EPR_INSET_NM"]) == 50
        assert ast.literal_eval(assignments["SURFACE_EPR_INSET_MARGINS_NM"]) == (
            0,
            50,
            100,
            200,
            500,
            1000,
        )
        assert ast.literal_eval(assignments["SURFACE_EPR_ACTIVE_INTERFACE_PRESET_NAMES"]) == (
            "martinis2022_ms",
        )

        assert '"interface_type": "MS"' in source
        assert '"interface_type": "MA"' not in source
        assert '"interface_type": "SA"' not in source
        assert "martinis2022_ma" not in source
        assert "martinis2022_sa" not in source
        assert "substrate_air_surface_epr_specs" not in source
        assert "SURFACE_EPR_BOUNDARY_INTERFACE_PRESETS" not in source
        assert "get_gsim_palace_simulation_layer_catalog" not in source
        assert "add_source_surface_epr_regions(" not in source
        assert "build_source_surface_epr" not in source
        assert "sim.set_simulation_layers(surface_epr_catalog)" not in source
        assert "build_interface_surface_catalog(mesh_result.groups)" not in source
        assert "build_surface_epr_dielectric_specs(" not in source
        assert "build_postprocessing_config_from_manifest(" not in source
        assert "postprocessing=postprocessing" not in source
        assert "sim.set_surface_epr(" in source
        assert f'representation="{representation}"' in source
        assert "inset_margins_um=SURFACE_EPR_INSET_MARGINS_UM" in source
        assert '"preset_name": "martinis2022_ms"' in source
        assert '"face_kind": "bottom"' in source


def test_surface_epr_b_notebooks_activate_ms_ma_sa() -> None:
    for notebook in (SURFACE_EPR_B_HANDOFF_NOTEBOOK, SURFACE_EPR_B_LOCAL_NOTEBOOK):
        source = notebook.read_text()
        _assert_b_ms_ma_sa_notebook(source)


def _assert_b_ms_ma_sa_notebook(source: str) -> None:
    assignments = _assignments(source)

    assert ast.literal_eval(assignments["SURFACE_EPR_ACTIVE_INTERFACE_PRESET_NAMES"]) == (
        "martinis2022_ms",
        "Woods2019_Si_MA",
        "Woods2019_Si_SA",
    )
    assert '"interface_type": "MS"' in source
    assert "Woods2019_Si_MA" in source
    assert "Woods2019_Si_SA" in source
    assert "deferred_loss_channels" not in source
    assert "sim.set_surface_epr(" in source
    assert 'representation="B"' in source
    assert '"preset_name": "martinis2022_ms"' in source
    assert '"preset_name": "Woods2019_Si_MA"' in source
    assert '"preset_name": "Woods2019_Si_SA"' in source
    assert '"face_kind": "bottom"' in source
    assert '"face_kind": ("top", "sidewall")' in source
    assert '"face_kind": "top"' in source
    assert '"surface_epr_interfaces": ("MS bottom", "MA top", "MA sidewall", "SA top")' in source
    assert '"active_loss_channels": ("MA", "MS", "SA")' in source


def test_surface_epr_c_notebook_validates_route_c_interfaces() -> None:
    source = SURFACE_EPR_C_NOTEBOOK.read_text()
    assignments = _assignments(source)

    assert ast.literal_eval(assignments["SURFACE_EPR_INSET_NM"]) == 50
    assert ast.literal_eval(assignments["SURFACE_EPR_INSET_MARGINS_NM"]) == (
        0,
        50,
        100,
        200,
        500,
        1000,
    )
    assert ast.literal_eval(assignments["SURFACE_EPR_ACTIVE_INTERFACE_PRESET_NAMES"]) == (
        "martinis2022_ms",
        "Woods2019_Si_MA",
        "Woods2019_Si_SA",
    )

    assert '"interface_type": "MS"' in source
    assert '"interface_type": "MA"' not in source
    assert '"interface_type": "SA"' not in source
    assert "Woods2019_Si_MA" in source
    assert "Woods2019_Si_SA" in source
    assert "build_interface_surface_catalog(mesh_result.groups)" not in source
    assert "build_surface_epr_dielectric_specs(" not in source
    assert "build_postprocessing_config_from_manifest(" not in source
    assert "postprocessing=postprocessing" not in source
    assert "sim.set_surface_epr(" in source
    assert 'representation="C"' in source
    assert "inset_margins_um=SURFACE_EPR_INSET_MARGINS_UM" in source
    assert '"preset_name": "martinis2022_ms"' in source
    assert '"face_kind": "bottom"' in source
    assert '"face_kind": ("top", "sidewall")' in source
    assert 'port_name="o_mesh_positive_electrode"' in source
    assert 'physical_label="positive"' in source
    assert '"validated_mesh_interface_types": ("MA", "MS", "SA")' in source
    assert '"active_loss_channels": ("MA", "MS", "SA")' in source
    assert "SURFACE_EPR_RETAIN_3D_METAL_VOLUME = True" in source
    assert "SURFACE_EPR_PLANAR_CONDUCTORS = False" in source
    assert "generated_child_physical_group_examples" in source
    assert '"deferred_route_c_inset": "requires shared-face fragmentation"' not in source


def test_surface_epr_local_notebook_uses_route_b_full_3d_reference_topology() -> None:
    source = SURFACE_EPR_B_LOCAL_NOTEBOOK.read_text()

    assert "SURFACE_EPR_USE_FINITE_METAL_SHELL" not in source
    assert "SURFACE_EPR_PLANAR_CONDUCTORS = False" in source
    assert "planar_conductors=True" not in source
    assert '"finite_shell_route_b"' in source
    assert '"surface_epr_interfaces"' in source
    assert "inset_margins_um=SURFACE_EPR_INSET_MARGINS_UM" in source


def test_surface_epr_docs_are_conclusion_first_and_scoped() -> None:
    docs = "\n".join(
        [
            Path("docs/developing-features.md").read_text(),
            Path("docs/notebooks.rst").read_text(),
        ]
    )

    assert "Fast Review Conclusions" in docs
    assert "Surface EPR A/B/C representation notebooks" in docs
    assert "Route B finite-metal shell Surface EPR" in docs
    assert "local B activates public MS/MA/SA presets for comparison" in docs
    assert "Route B finite-metal shell Surface EPR local test" in docs
    assert "public_surface_epr_ribbon_capacitor_representation_a_workflow.py" in docs
    assert "public_surface_epr_ribbon_capacitor_workflow.py" in docs
    assert "public_surface_epr_ribbon_capacitor_representation_c_workflow.py" in docs
    assert "public_surface_epr_ribbon_capacitor_representation_b_local_workflow.py" in docs
    assert "calibrated process-default MA/SA policy" in docs
    assert "Route C retained-volume Surface EPR inset validation" in docs
