"""Generated AEDT handoff package template renderers.

This module owns the README, requirements, package-local Python runner, and
shell launcher text copied into AEDT handoff packages. It does not validate
source artifacts or write package directories.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from importlib.resources import files
from typing import Any

from orpen_sc_pdk.simulation.aedt.models import AedtNativePackageSpec


def render_aedt_package_readme(
    spec: AedtNativePackageSpec, case_rows: Sequence[Mapping[str, Any]]
) -> str:
    recipe_count = sum(len(row["recipes"]) for row in case_rows)
    hpc_resource = spec.resolved_hpc_resource()
    return f"""# AEDT Native Simulation Package

Project: `{spec.project_name}`

This package imports GDS plus XML control artifacts into AEDT through PyAEDT
and dispatches solver recipes for HFSS Driven Terminal, HFSS Eigenmode, Q3D,
and Q2D.

## Contents

- `manifest.yaml`: package source of truth.
- `gds/`: scene-level GDS files.
- `tech/`: AEDT GDS import XML control files plus TECH audit sidecars.
- `layer_mapping/`: source layer audit sidecars.
- `metadata/`: solver-family sidecars such as Q2D conductor markers.
- `hpc/`: generated AEDT HPC configuration files for point-local workers.
- `scripts/run_aedt_native.py`: PyAEDT automation entrypoint.
- `scripts/run_aedt_q2d_cross_section.py`: Q2D cross-section workflow entrypoint.
- `scripts/run_aedt_native.sh`: Ubuntu launcher.
- `scripts/run_aedt_native.ps1`: Windows launcher.

## Summary

- Cases: {len(case_rows)}
- Recipes: {recipe_count}
- Platform: `{spec.platform}`
- Runtime AEDT version: `{spec.runtime.aedt_version or "auto-detect"}`
- Runtime gRPC mode: `{spec.runtime.grpc_mode}`
- AEDT worker cores: `{hpc_resource.num_cores}`
- AEDT max workers: `{hpc_resource.max_workers}`

After extracting the handoff archive, run from the AEDT package directory:

```bash
cd <run_or_sweep_id>/exports/aedt_native
./scripts/run_aedt_native.sh --import
```

The target machine needs AEDT, a local AEDT license, `uv`, and an isolated
Python environment with PyAEDT. It does not need the `orpen-sc-pdk` checkout
once this package has been generated.

Prepare the package-local runtime from the AEDT package directory:

```bash
uv python install 3.12
uv venv --python 3.12 .venv-aedt
source .venv-aedt/bin/activate
uv pip install -r requirements-aedt.txt
python -c "from ansys.aedt.core import Hfss, Q2d; import yaml; print('PyAEDT ok')"
```

Import mode ensures the model, assignments, and setup exist without solving.
Solve mode reopens the same project, repairs safe settings, solves, and exports
matrices when the selected recipe supports those operations:

```bash
./scripts/run_aedt_native.sh --import
./scripts/run_aedt_native.sh --solve
```
"""


def render_aedt_requirements() -> str:
    return """pyaedt[all]==0.26.2
pyyaml>=6.0
"""


def render_shell_launcher() -> str:
    return """#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python "$SCRIPT_DIR/run_aedt_native.py" "$@"
"""


def render_powershell_launcher() -> str:
    return """param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]] $Args
)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
python (Join-Path $ScriptDir "run_aedt_native.py") @Args
"""


def render_q2d_runner_script() -> str:
    return r'''"""Run the Q2D cross-section workflow from an AEDT-native package."""

from __future__ import annotations

from run_aedt_native import (
    apply_q2d_section_workflow as _apply_q2d_section_workflow,
    build_q2d_native_2d_geometry_plan as _build_q2d_native_2d_geometry_plan,
    export_q2d_matrices as _export_q2d_matrices,
    load_q2d_conductor_rows as _load_q2d_conductor_rows,
    main as _native_main,
    q2d_conductor_groups as _q2d_conductor_groups,
    run_q2d_extraction as _run_q2d_extraction,
)


def load_q2d_conductor_rows(*args, **kwargs):
    return _load_q2d_conductor_rows(*args, **kwargs)


def q2d_conductor_groups(*args, **kwargs):
    return _q2d_conductor_groups(*args, **kwargs)


def apply_q2d_section_workflow(*args, **kwargs):
    return _apply_q2d_section_workflow(*args, **kwargs)


def build_q2d_native_2d_geometry_plan(*args, **kwargs):
    return _build_q2d_native_2d_geometry_plan(*args, **kwargs)


def run_q2d_extraction(*args, **kwargs):
    return _run_q2d_extraction(*args, **kwargs)


def export_q2d_matrices(*args, **kwargs):
    return _export_q2d_matrices(*args, **kwargs)


def main():
    _native_main()


if __name__ == "__main__":
    main()
'''


def render_runtime_runner() -> str:
    return _runtime_bundle_text("run_aedt_native.py")


def _runtime_bundle_text(name: str) -> str:
    return (
        files("orpen_sc_pdk.simulation.aedt.runtime_bundle")
        .joinpath(name)
        .read_text(encoding="utf-8")
    )


__all__ = [
    "render_aedt_package_readme",
    "render_aedt_requirements",
    "render_powershell_launcher",
    "render_q2d_runner_script",
    "render_runtime_runner",
    "render_shell_launcher",
]
