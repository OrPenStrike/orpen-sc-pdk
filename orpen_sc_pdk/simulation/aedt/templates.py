"""Generated AEDT handoff package template renderers.

This module owns the README, requirements, package-local Python entrypoints,
and shell launcher text copied into AEDT handoff packages. It does not validate
source artifacts or write package directories.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
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
- `gds/`: scene-level GDS files when the package is layout-backed.
- `tech/`: AEDT GDS import XML control files when the package is layout-backed.
- `layer_mapping/`: source layer audit sidecars when the package is layout-backed.
- `metadata/`: solver-family sidecars such as Q2D conductor markers.
- `hpc/`: generated AEDT HPC configuration files for point-local workers.
- `scripts/run_aedt_native.py`: thin Python entrypoint.
- `scripts/runtime_bundle/`: run-side PyAEDT automation package copied into
  this handoff package.
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
cd aedt_native
./scripts/run_aedt_native.sh --mode import
```

## Target Machine Setup

This package is portable across AEDT machines. The target machine does not need
the source repository or adjacent public PDK checkouts. It does need AEDT, a
local AEDT license, `uv`, and an isolated Python environment with PyAEDT.

Extract the archive so the AEDT package directory is the top-level directory,
then enter it:

```bash
tar -xzf <run_or_sweep_id>-aedt.tar.gz
cd aedt_native
```

Prepare the package-local runtime from the AEDT package directory:

```bash
uv python install 3.12
uv venv --python 3.12 .venv-aedt
source .venv-aedt/bin/activate
uv pip install -r requirements-aedt.txt
python -c "from ansys.aedt.core import Hfss, Q2d; import yaml; print('PyAEDT ok')"
```

The shell launcher uses `${{PYTHON:-python3}}`. Activate `.venv-aedt`, or set
`PYTHON=/path/to/python`, before running the package unless you intentionally
use another PyAEDT environment.

Import mode ensures the model, assignments, and setup exist without solving.
Incremental Q2D reruns detect existing stages. Solve mode reopens the same
project, skips valid stages, repairs safe settings, then solves and exports
matrices when the selected recipe supports those operations:

```bash
./scripts/run_aedt_native.sh --mode import
./scripts/run_aedt_native.sh --mode solve
```

The short commands load generated defaults from `run_configs/import.yaml` and
`run_configs/solve.yaml`. Explicit command-line arguments still override those
config values. For Q2D point-local sweeps, import and solve use per-point AEDT
worker projects; inspect the actual solve model under:

```text
points/<point_slug>/aedt_project/<project>.aedt
```

Parallel workers finish out of order, so progress is one total point-level bar
with sweep-axis coverage rather than one progress bar per sweep axis. Parent
progress writes to `logs/parallel_progress.jsonl`; each worker captures stdout
under `logs/workers/<point>__<recipe>/worker_stdout.log`, and each point keeps
its own `logs/<point>/<recipe>/progress.jsonl`.

Use `--force-rebuild` only when you intentionally want to clear recipe-owned
AEDT geometry and setup before rebuilding:

```bash
./scripts/run_aedt_native.sh --mode import --force-rebuild
```

The generated runner defaults to non-graphical AEDT startup and local-auto
gRPC. On Linux AEDT 2024 R2 systems without the secure local service pack,
PyAEDT starts through the local UDS path and AEDT falls back to insecure mode.
Use `--graphical` only when the target AEDT machine should show Desktop. Use
`--grpc-secure` only when forcing secure gRPC is required and supported. Use
`--grpc-insecure` only for explicit TCP `InsecureMode`; that mode is not the
local-auto default.

Solver outputs are written inside this package at
`points/<point_slug>/<recipe_id>/`, AEDT projects are written to
`points/<point_slug>/aedt_project/`, and logs/audit files are written to
package-local `logs/`.

After AEDT finishes, return data with the light result profile. It keeps
analysis inputs and excludes solver handoff inputs plus heavyweight AEDT project
state:

```bash
cd aedt_native
BUNDLE_ID="$(basename "$PWD")"
INCLUDE_PATHS=()
for path in manifest.yaml points.csv points.json README.md metadata logs results points; do
  [ -e "$path" ] && INCLUDE_PATHS+=("$path")
done
tar \
  --checkpoint=1000 \
  --checkpoint-action=dot \
  -czf "../${{BUNDLE_ID}}-aedt-results-light.tar.gz" \
  --transform "s|^|${{BUNDLE_ID}}/|" \
  --exclude='exports' \
  --exclude='exports/*' \
  --exclude='points/*/exports' \
  --exclude='points/*/exports/*' \
  --exclude='points/*/geometry' \
  --exclude='points/*/geometry/*' \
  --exclude='points/*/metadata' \
  --exclude='points/*/metadata/*' \
  --exclude='points/*/logs' \
  --exclude='points/*/logs/*' \
  --exclude='points/*/results' \
  --exclude='points/*/results/*' \
  --exclude='points/*/config.json' \
  --exclude='points/*/manifest.json' \
  --exclude='points/*/README.md' \
  --exclude='points/*/palace.msh' \
  --exclude='points/*/mesh.msh' \
  --exclude='geometry' \
  --exclude='geometry/*' \
  --exclude='*.tar.gz' \
  --exclude='*.tar.zst' \
  --exclude='*.tgz' \
  --exclude='__pycache__' \
  --exclude='*/__pycache__/*' \
  --exclude='.ipynb_checkpoints' \
  --exclude='*/.ipynb_checkpoints/*' \
  --exclude='*/aedt_project' \
  --exclude='*/aedt_project/*' \
  --exclude='*.aedt' \
  --exclude='*.aedt.lock' \
  --exclude='*.aedtresults' \
  --exclude='*.aedtresults/*' \
  "${{INCLUDE_PATHS[@]}}"
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
PYTHON_BIN="${PYTHON:-python3}"
exec "$PYTHON_BIN" "$SCRIPT_DIR/run_aedt_native.py" "$@"
"""


def render_powershell_launcher() -> str:
    return """param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]] $Args
)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
python (Join-Path $ScriptDir "run_aedt_native.py") @Args
"""


def render_runtime_runner() -> str:
    return '''"""Run the package-local AEDT runtime bundle."""

from __future__ import annotations

from runtime_bundle.run_aedt_native import main as _runtime_main


def main() -> None:
    _runtime_main()


if __name__ == "__main__":
    main()
'''


__all__ = [
    "render_aedt_package_readme",
    "render_aedt_requirements",
    "render_powershell_launcher",
    "render_runtime_runner",
    "render_shell_launcher",
]
