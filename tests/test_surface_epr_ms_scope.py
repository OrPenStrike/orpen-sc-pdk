"""Surface EPR notebook scope tests.

Responsibility:
Owns the public notebook contract for the current ThinMetal MS-only Surface EPR
slice.
Does not own broader MA/SA interface policy, raw-mesh interface banding, or
Palace report parsing.
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

        assert ast.literal_eval(assignments["SURFACE_EPR_CUTOFFS_NM"]) == [
            50,
            100,
            200,
            500,
            1000,
        ]
        assert ast.literal_eval(assignments["SURFACE_EPR_SOURCE_SHEETS"]) == (
            "D0_TOP_M1_pec_0",
            "D0_TOP_M1_pec_1",
        )
        assert ast.literal_eval(
            assignments["SURFACE_EPR_SOURCE_INTERFACE_PRESET_NAMES"]
        ) == ("martinis2022_ms",)

        assert '"interface_type": "MS"' in source
        assert '"interface_type": "MA"' not in source
        assert '"interface_type": "SA"' not in source
        assert "martinis2022_ma" not in source
        assert "martinis2022_sa" not in source
        assert "substrate_air_surface_epr_specs" not in source
        assert "SURFACE_EPR_BOUNDARY_INTERFACE_PRESETS" not in source
        assert "get_gsim_palace_simulation_layer_catalog" not in source
        assert "sim.set_simulation_layers(surface_epr_catalog)" in source
        assert "dielectric_interfaces=source_aware_surface_epr_specs" in source


def test_surface_epr_docs_are_conclusion_first_and_scoped() -> None:
    docs = "\n".join(
        [
            Path("docs/developing-features.md").read_text(),
            Path("docs/notebooks.rst").read_text(),
        ]
    )

    assert "Fast Review Conclusions" in docs
    assert "ThinMetal source-aware Surface EPR margin groups, MS-only" in docs
    assert "public_surface_epr_ribbon_capacitor_workflow.py" in docs
    assert "public_surface_epr_ribbon_capacitor_local_workflow.py" in docs
    assert "MA/SA and general 3D interface banding are deferred" in docs
