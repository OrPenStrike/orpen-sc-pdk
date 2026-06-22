"""Surface EPR notebook scope tests.

Responsibility:
Owns the public notebook contract for the current Route B MS-only Surface EPR slices.
Does not own broader MA/SA interface policy or Palace report parsing.
Source of Truth: docs/notebooks.rst and docs/developing-features.md.
"""

from __future__ import annotations

import ast
from pathlib import Path

SURFACE_EPR_NOTEBOOKS = (
    Path("notebooks/src/public_surface_epr_ribbon_capacitor_workflow.py"),
    Path("notebooks/src/public_surface_epr_ribbon_capacitor_local_workflow.py"),
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


def test_surface_epr_notebooks_are_ms_only() -> None:
    for notebook in SURFACE_EPR_NOTEBOOKS:
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
        assert ast.literal_eval(
            assignments["SURFACE_EPR_ACTIVE_INTERFACE_PRESET_NAMES"]
        ) == ("martinis2022_ms",)

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
        assert "build_interface_surface_catalog(mesh_result.groups)" in source
        assert "dielectric_interfaces=surface_epr_dielectric_specs" in source


def test_surface_epr_local_notebook_uses_route_b_finite_shell() -> None:
    source = Path(
        "notebooks/src/public_surface_epr_ribbon_capacitor_local_workflow.py"
    ).read_text()

    assert "SURFACE_EPR_USE_FINITE_METAL_SHELL = True" in source
    assert "SURFACE_EPR_PLANAR_CONDUCTORS = not SURFACE_EPR_USE_FINITE_METAL_SHELL" in source
    assert "DielectricInterfaceSpec(" in source
    assert '"finite_shell_route_b"' in source
    assert '"conductor_surface"' in source
    assert '"surface_epr_ms_bottom_entries"' in source
    assert "surface_epr_inset_margins_um=SURFACE_EPR_INSET_MARGINS_UM" in source


def test_surface_epr_docs_are_conclusion_first_and_scoped() -> None:
    docs = "\n".join(
        [
            Path("docs/developing-features.md").read_text(),
            Path("docs/notebooks.rst").read_text(),
        ]
    )

    assert "Fast Review Conclusions" in docs
    assert "Route B finite-metal shell Surface EPR, MS-bottom selection" in docs
    assert "Route B finite-metal shell Surface EPR local test" in docs
    assert "public_surface_epr_ribbon_capacitor_workflow.py" in docs
    assert "public_surface_epr_ribbon_capacitor_local_workflow.py" in docs
    assert "MA/SA reporting and non-planar geodesic inset bands are deferred" in docs
