"""Inset Surface EPR demo notebook contract checks.

Responsibility:
Owns the public demo notebook file contract for Martinis 2022 ribbon A/B/C
local, no-inset local, and F1 handoff examples.
Does not own gsim Surface EPR lowering, Palace execution, or report parsing.
Source of Truth: notebooks/src/Inset_Surface_EPR_Demo/.
"""

from __future__ import annotations

import ast
from pathlib import Path

DEMO_ROOT = Path("notebooks/src/Inset_Surface_EPR_Demo")
NOTEBOOK_ROOT = Path("notebooks/Inset_Surface_EPR_Demo")


def _assignments(path: Path) -> dict[str, ast.expr]:
    tree = ast.parse(path.read_text())
    return {
        target.id: node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }


def test_inset_surface_epr_demo_has_route_mode_notebooks() -> None:
    expected = {
        f"martinis2022_ribbon_route_{route}_{mode}.py"
        for route in ("a", "b", "c")
        for mode in ("local", "hpc_handoff")
    }
    expected.update(
        {
            f"martinis2022_ribbon_route_{route}_no_inset_local.py"
            for route in ("a", "b", "c")
        }
    )

    assert {path.name for path in DEMO_ROOT.glob("*.py")} == expected
    assert {path.name for path in NOTEBOOK_ROOT.glob("*.ipynb")} == {
        name.removesuffix(".py") + ".ipynb" for name in expected
    }


def test_inset_surface_epr_demo_uses_consistent_solver_and_material_policy() -> None:
    for path in DEMO_ROOT.glob("*.py"):
        source = path.read_text()
        assignments = _assignments(path)

        assert ast.literal_eval(assignments["PALACE_ORDER"]) == 3
        assert ast.literal_eval(assignments["LOCAL_MAX_ITS"]) == 3
        assert ast.literal_eval(assignments["HPC_MAX_ITS"]) == 15
        assert ast.literal_eval(assignments["PALACE_UPDATE_FRACTION"]) == 0.3
        expected_margins_nm = (
            (0,)
            if path.name.endswith("_no_inset_local.py")
            else (0, 50, 100, 200, 500, 1000)
        )
        assert ast.literal_eval(assignments["SURFACE_EPR_INSET_MARGINS_NM"]) == (
            expected_margins_nm
        )
        assert ast.literal_eval(assignments["SURFACE_EPR_ACTIVE_INTERFACE_PRESET_NAMES"]) == (
            "martinis2022_ms",
            "Woods2019_Si_MA",
            "Woods2019_Si_SA",
        )
        assert "sim.set_surface_epr(" in source
        assert '"MS": {' in source and '"MA": {' in source and '"SA": {' in source
        assert "planar_conductors=SURFACE_EPR_PLANAR_CONDUCTORS" in source
        assert '"centroid": entry.metadata.get("centroid")' in source
        assert '"dielectric_postprocessing_row_counts"' in source


def test_inset_surface_epr_demo_splits_local_and_handoff_controls() -> None:
    for path in DEMO_ROOT.glob("*_local.py"):
        source = path.read_text()
        assert 'DEMO_MODE = "local"' in source
        assert "PALACE_RUN_LOCAL" in source
        assert "resolve_public_palace_run_profile" not in source

    for path in DEMO_ROOT.glob("*_hpc_handoff.py"):
        source = path.read_text()
        assert 'DEMO_MODE = "hpc_handoff"' in source
        assert 'PALACE_HPC_PROFILE = "f1:ct112"' in source
        assert '"memory_mb": 524288' in source
        assert "write_slurm_sbatch_handoff" in source
