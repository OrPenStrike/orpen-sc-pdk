"""Run-side manifest, path, and audit I/O for AEDT handoff packages.

This module is copied with ``runtime_bundle`` into generated AEDT handoff
packages and executed on the target AEDT machine. It owns package-relative path
resolution, run-config loading, output-root discovery, JSON/JSONL audit writes,
and deterministic source hashing. It does not own solver decisions or package
writer layout semantics.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

RUN_CONFIG_CLI_FLAGS = {
    "resume_policy": ("--resume-policy",),
    "skip_completed": ("--skip-completed", "--no-skip-completed"),
    "continue_on_failure": ("--continue-on-failure", "--stop-on-failure"),
    "parallel": ("--parallel", "--no-parallel"),
    "max_workers": ("--max-workers",),
    "num_cores": ("--num-cores",),
    "memory_mb_total": ("--memory-mb-total",),
    "memory_mb_per_worker": ("--memory-mb-per-worker",),
    "ram_percent": ("--ram-percent",),
    "core_budget": ("--core-budget",),
    "progress": ("--progress",),
    "progress_interval_seconds": ("--progress-interval-seconds",),
}
RUN_CONFIG_ALLOWED_KEYS = {"mode", *RUN_CONFIG_CLI_FLAGS}


def load_manifest(path: str | Path) -> dict[str, Any]:
    """Load an AEDT package manifest from the run-side package.

    The manifest is the target-machine source of truth for project path, cases,
    runtime policy, and recipe dispatch. YAML parsing is intentionally strict at
    this boundary: the caller gets the parsed payload, and solver-specific
    validation stays with solver code.
    """

    with Path(path).open(encoding="utf-8") as file:
        data = yaml.safe_load(file)
    if not isinstance(data, dict):
        raise RuntimeError(f"AEDT manifest must be a mapping: {path}")
    _validate_manifest(data, path)
    return data


def _validate_manifest(manifest: dict[str, Any], path: str | Path) -> None:
    if manifest.get("schema_version") != 1:
        raise RuntimeError(f"AEDT manifest {path} must use schema_version: 1")
    for key in ("project", "execution", "runtime", "hpc"):
        if not isinstance(manifest.get(key), dict):
            raise RuntimeError(f"AEDT manifest {path} field {key!r} must be a mapping")
    project = manifest["project"]
    for key in ("name", "path", "platform"):
        if not str(project.get(key) or "").strip():
            raise RuntimeError(f"AEDT manifest {path} project.{key} is required")
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        raise RuntimeError(f"AEDT manifest {path} requires at least one case")
    for case in cases:
        if not isinstance(case, dict):
            raise RuntimeError(f"AEDT manifest {path} cases must contain mappings")
        if not str(case.get("id") or "").strip():
            raise RuntimeError(f"AEDT manifest {path} case.id is required")
        recipes = case.get("recipes")
        if not isinstance(recipes, list) or not recipes:
            raise RuntimeError(f"AEDT manifest {path} case {case.get('id')!r} needs recipes")
        layout_recipes = [
            recipe
            for recipe in recipes
            if isinstance(recipe, dict)
            and (
                recipe.get("type") != "q2d_extraction"
                or recipe.get("q2d_geometry_mode") != "semantic_cross_section"
            )
        ]
        if not layout_recipes:
            if not str(case.get("q2d_cross_section") or "").strip():
                raise RuntimeError(
                    f"AEDT manifest {path} semantic Q2D case.q2d_cross_section is required"
                )
        elif any(recipe.get("type") == "q3d_extraction" for recipe in layout_recipes):
            for key in ("gds", "layer_mapping_json"):
                if not str(case.get(key) or "").strip():
                    raise RuntimeError(
                        f"AEDT manifest {path} direct-GDS Q3D case.{key} is required"
                    )
        if any(recipe.get("type") != "q3d_extraction" for recipe in layout_recipes):
            for key in ("gds", "tech"):
                if not str(case.get(key) or "").strip():
                    raise RuntimeError(f"AEDT manifest {path} case.{key} is required")
        for recipe in recipes:
            if not isinstance(recipe, dict):
                raise RuntimeError(f"AEDT manifest {path} recipes must contain mappings")
            for key in ("id", "type", "design_name"):
                if not str(recipe.get(key) or "").strip():
                    raise RuntimeError(f"AEDT manifest {path} recipe.{key} is required")
            if recipe.get("type") == "q3d_extraction":
                _validate_q3d_region_recipe(recipe, path)


def _validate_q3d_region_recipe(recipe: dict[str, Any], path: str | Path) -> None:
    """Reject direct-GDS Q3D manifests without an explicit six-sided vacuum Region."""

    region = recipe.get("q3d_region")
    if not isinstance(region, dict):
        raise RuntimeError(f"AEDT manifest {path} q3d_extraction recipe.q3d_region is required")
    if str(region.get("padding_type") or "") != "Absolute Offset":
        raise RuntimeError(
            f"AEDT manifest {path} Q3D Region requires padding_type='Absolute Offset'"
        )
    if str(region.get("material") or "").casefold() != "vacuum":
        raise RuntimeError(f"AEDT manifest {path} Q3D Region material must be Vacuum")
    padding = region.get("padding")
    directions = {"+X", "-X", "+Y", "-Y", "+Z", "-Z"}
    if not isinstance(padding, dict) or set(padding) != directions:
        raise RuntimeError(
            f"AEDT manifest {path} Q3D Region requires exactly six padding directions"
        )
    if any(not str(value).strip() for value in padding.values()):
        raise RuntimeError(f"AEDT manifest {path} Q3D Region padding values must not be empty")


def package_path(package_root: str | Path, relative: str | Path) -> Path:
    """Resolve a manifest-relative path inside the handoff package."""

    return (Path(package_root) / relative).resolve()


def cli_option_present(raw_args: list[str] | tuple[str, ...], *flags: str) -> bool:
    """Return whether any CLI flag was explicitly supplied by the operator."""

    return any(arg == flag or arg.startswith(f"{flag}=") for arg in raw_args for flag in flags)


def resolve_requested_mode(args: Any) -> str:
    """Resolve import/solve mode from CLI aliases and the canonical option."""

    requested = []
    if getattr(args, "import_mode", False):
        requested.append("import")
    if getattr(args, "solve_mode", False):
        requested.append("solve")
    if args.mode is not None:
        requested.append(args.mode)
    if len(set(requested)) > 1:
        raise RuntimeError("Conflicting mode flags were provided.")
    return requested[0] if requested else "import"


def run_config_path_for_mode(manifest: dict[str, Any], manifest_path: Path, mode: str) -> Path:
    """Return the package-local run-config path for a resolved mode."""

    execution = manifest.get("execution") if isinstance(manifest, dict) else {}
    key = f"{mode}_config"
    configured = execution.get(key) if isinstance(execution, dict) else None
    if configured:
        return package_path(manifest_path.parent, configured)
    return manifest_path.parent / "run_configs" / f"{mode}.yaml"


def load_run_config(path: str | Path, *, mode: str) -> dict[str, Any]:
    """Load and validate one import/solve run-config file.

    Raises:
        RuntimeError: The config is missing, not a mapping, has unknown keys, or
            declares a different mode than the requested runner mode.
    """

    path = Path(path)
    if not path.is_file():
        raise RuntimeError(f"Missing AEDT {mode} run config: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise RuntimeError(f"AEDT run config must be a mapping: {path}")
    unknown = sorted(set(data) - RUN_CONFIG_ALLOWED_KEYS)
    if unknown:
        raise RuntimeError(f"AEDT run config {path} has unsupported keys: {unknown}")
    configured_mode = data.get("mode")
    if configured_mode is not None and configured_mode != mode:
        raise RuntimeError(f"AEDT run config {path} is for mode {configured_mode!r}, not {mode!r}")
    return data


def apply_run_config(args: Any, manifest: dict[str, Any], manifest_path: Path, raw_args: list[str]):
    """Apply generated run-config defaults without overriding explicit CLI flags."""

    args.mode = resolve_requested_mode(args)
    config_path = run_config_path_for_mode(manifest, manifest_path, args.mode)
    config = load_run_config(config_path, mode=args.mode)
    args._aedt_run_config_path = str(config_path) if Path(config_path).is_file() else None
    args._aedt_run_config = dict(config)
    for key, value in config.items():
        if key == "mode":
            continue
        flags = RUN_CONFIG_CLI_FLAGS.get(key, ())
        if flags and cli_option_present(raw_args, *flags):
            continue
        setattr(args, key, value)
    return args


def resolve_output_roots(args: Any, package_root: str | Path) -> dict[str, Any]:
    """Resolve point-output and log roots for a copied handoff package."""

    package_root = Path(package_root)
    run_root = None
    if args.results_root:
        results_root = Path(args.results_root).resolve()
        results_source = "cli"
    else:
        results_root = package_root / "points"
        results_source = "package_points"

    if args.logs_root:
        logs_root = Path(args.logs_root).resolve()
        logs_source = "cli"
    else:
        logs_root = package_root / "logs"
        logs_source = "package"

    return {
        "run_root": run_root,
        "results_root": results_root,
        "results_root_source": results_source,
        "logs_root": logs_root,
        "logs_root_source": logs_source,
    }


def infer_run_root(package_root: str | Path) -> Path | None:
    """Compatibility hook for old callers; AEDT packages now run in-place."""

    return None


def write_json(path: str | Path, payload: Any) -> None:
    """Write an indented JSON audit artifact."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def append_jsonl(path: str | Path, payload: Any) -> None:
    """Append a stable JSONL audit row."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, sort_keys=True))
        file.write("\n")


def read_json(path: str | Path) -> Any:
    """Read JSON when present; return ``None`` for absent optional artifacts."""

    path = Path(path)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def stable_json(payload: Any) -> str:
    """Serialize a payload for hashing independent of dictionary insertion order."""

    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def sha256_text(text: Any) -> str:
    """Hash text for run-side state records."""

    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def file_sha256(path: str | Path) -> str:
    """Hash a source sidecar file in chunks for state validation."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = [
    "append_jsonl",
    "apply_run_config",
    "cli_option_present",
    "file_sha256",
    "infer_run_root",
    "load_manifest",
    "load_run_config",
    "package_path",
    "read_json",
    "resolve_output_roots",
    "resolve_requested_mode",
    "run_config_path_for_mode",
    "sha256_text",
    "stable_json",
    "write_json",
]
