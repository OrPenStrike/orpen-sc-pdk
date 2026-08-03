"""Run-side CLI entrypoint for generated AEDT handoff packages.

This file is copied into ``scripts/runtime_bundle`` and is invoked by the thin
``scripts/run_aedt_native.py`` launcher. It owns argument parsing, run-config
application, preflight evidence, serial recipe iteration, worker-mode recipe
execution, and dispatch into point-local parallel orchestration.

Boundary notes:
- AEDT lifecycle is delegated to ``session.py``.
- Manifest/path/hash/audit helpers are delegated to ``io.py``.
- Material creation and object binding are delegated to ``materials.py``.
- Parent-process parallel sweep orchestration is delegated to ``sweep.py``.
- Solver-specific implementation still lives here as a transitional v1 boundary.
  The ``solver/*`` modules reserve the target folder structure and must fail
  fast until those implementations are moved there.

This module is a main entrypoint, not just a worker. In parallel mode the parent
uses ``sweep.py`` to start subprocesses that call this same file with
``--worker-mode``.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import sys
import threading
import time
import traceback
from decimal import Decimal
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
for _candidate in (_SCRIPT_DIR.parent, _SCRIPT_DIR.parent.parent):
    if (_candidate / "runtime_bundle").is_dir() and str(_candidate) not in sys.path:
        sys.path.insert(0, str(_candidate))

from runtime_bundle.io import (
    append_jsonl,
    apply_run_config,
    file_sha256,
    load_manifest,
    package_path,
    read_json,
    resolve_output_roots,
    sha256_text,
    stable_json,
    write_json,
)
from runtime_bundle.materials import (
    ensure_aedt_project_materials,
    layer_number_from_object_name,
    load_aedt_material_context,
    material_context_binding_for_object_name,
    material_context_bindings,
    material_context_compiled_materials,
    material_context_material_for_row,
)
from runtime_bundle.session import (
    AEDT_MODELER_UNIT_TO_UM,
    aedt_constructor_kwargs,
    collect_aedt_messages_from_app,
    collect_recent_aedt_messages,
    create_aedt_app,
    create_aedt_session,
    ensure_design_modeler_units,
    finalize_aedt_session,
    normalize_modeler_units,
    recipe_modeler_units,
    stop_aedt_simulations,
)
from runtime_bundle.sweep import (
    ParallelProgressReporter,
    apply_worker_project_isolation,
    format_parallel_axis_coverage,
    format_parallel_progress_line,
    latest_jsonl_row,
    parallel_stage_counts,
    parallel_worker_command,
    run_log_root,
    run_point_local_sweep,
    selected_manifest_cases,
    should_run_parallel_parent,
    should_skip_recipe_for_resume,
    worker_project_path,
)

run_parallel_package = run_point_local_sweep

__all__ = [
    "ParallelProgressReporter",
    "format_parallel_axis_coverage",
    "format_parallel_progress_line",
    "latest_jsonl_row",
    "parallel_stage_counts",
    "parallel_worker_command",
    "run_parallel_package",
    "worker_project_path",
]

AEDT_FREQUENCY_UNIT_TO_HZ = {
    "hz": Decimal("1"),
    "khz": Decimal("1e3"),
    "mhz": Decimal("1e6"),
    "ghz": Decimal("1e9"),
    "thz": Decimal("1e12"),
}
AEDT_Q2D_HPC_DESIGN_TYPE = "2D Extractor"
AEDT_HPC_DEFAULT_ALLOWED_DISTRIBUTION_TYPES = (
    "Variations",
    "Frequencies",
    "Mesh Assembly",
    "Transient Excitations",
    "Domain Solver",
)
AEDT_HPC_DEFAULT_RESOURCE = {
    "profile_name": "aedt-q2d-local",
    "machine_name": "localhost",
    "num_engines": 1,
    "num_cores": 4,
    "max_workers": 16,
    "core_budget": 64,
    "memory_mb_total": 240000,
    "memory_mb_per_worker": None,
    "ram_percent": None,
    "num_job_cores": 0,
    "num_gpus": 0,
    "use_auto_settings": True,
    "num_variations_to_distribute": 1,
    "allowed_distribution_types": list(AEDT_HPC_DEFAULT_ALLOWED_DISTRIBUTION_TYPES),
}
RECIPE_DISPATCH = {}


def recipe_handler(recipe_type):
    def decorator(func):
        RECIPE_DISPATCH[recipe_type] = func
        return func

    return decorator


def log(log_dir, message):
    log_dir.mkdir(parents=True, exist_ok=True)
    print(message, flush=True)
    with (log_dir / "aedt_messages.log").open("a", encoding="utf-8") as file:
        file.write(message)
        file.write("\n")


def preflight_payload(args, manifest, output_roots):
    validate_hpc_acf_override_contract(args)
    try:
        import ansys.aedt.core as aedt_core

        pyaedt_version = getattr(aedt_core, "__version__", "unknown")
    except Exception as exc:
        pyaedt_version = f"unavailable: {exc}"
    return {
        "python_executable": sys.executable,
        "python_version": sys.version,
        "pyaedt_version": pyaedt_version,
        "aedt_version": args.aedt_version,
        "project_path": manifest["project"]["path"],
        "canonical_project_path": manifest["project"].get("canonical_path"),
        "non_graphical": args.non_graphical,
        "parallel": args.parallel,
        "run_config_path": getattr(args, "_aedt_run_config_path", None),
        "worker_mode": args.worker_mode,
        "worker_project_path": getattr(args, "_aedt_worker_project_path", None),
        "worker_project_root": args.worker_project_root,
        "grpc_port": args.grpc_port,
        "new_desktop": args.new_desktop,
        "close_desktop": args.close_desktop,
        "force_rebuild": args.force_rebuild,
        "results_root_requested": args.results_root,
        "results_root_resolved": str(output_roots["results_root"]),
        "results_root_source": output_roots["results_root_source"],
        "logs_root_requested": args.logs_root,
        "logs_root_resolved": str(output_roots["logs_root"]),
        "logs_root_source": output_roots["logs_root_source"],
        "hpc": {
            "manifest": manifest.get("hpc"),
            "resolved_resource": resolve_runtime_hpc_resource(manifest, args),
            "acf_file_cli": args.acf_file,
        },
        **getattr(args, "_aedt_runtime_preflight", {}),
        "proxy_env": {
            name: os.environ.get(name)
            for name in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "no_proxy")
        },
    }


def write_preflight(logs_root, payload):
    write_json(logs_root / "aedt_preflight.json", payload)
    print("AEDT preflight:", json.dumps(payload, indent=2), flush=True)


def abort_worker_aedt_session(args):
    if args.grpc_port is None:
        raise RuntimeError("--abort-worker requires --grpc-port")
    from ansys.aedt.core import Desktop
    from ansys.aedt.core.generic.settings import settings

    if args.grpc_mode == "insecure":
        settings.grpc_secure_mode = False
    else:
        settings.grpc_secure_mode = True
    if args.grpc_local is not None:
        settings.grpc_local = str(args.grpc_local).casefold() == "true"
    desktop = Desktop(
        version=args.aedt_version,
        non_graphical=True,
        new_desktop=False,
        close_on_exit=False,
        machine="127.0.0.1",
        port=args.grpc_port,
    )
    try:
        result = desktop.stop_simulations(clean_stop=True)
        print(
            json.dumps(
                {
                    "event": "aedt_abort_sent",
                    "grpc_port": args.grpc_port,
                    "result": result,
                },
                indent=2,
            ),
            flush=True,
        )
    finally:
        desktop.release_desktop(close_projects=False, close_on_exit=False)


def import_gds_layout(case, recipe, manifest, package_root, result_dir, log_dir, args):
    from ansys.aedt.core import Hfss3dLayout

    project_path = manifest["project"]["path"]
    aedb_path = result_dir / f"{case['id']}_{recipe['id']}.aedb"
    control_relative = case.get("control") or case["tech"]
    control_path = package_path(package_root, control_relative)
    log(
        log_dir,
        (
            f"Importing GDS={case['gds']} control={control_relative} "
            f"project={project_path} design={recipe['design_name']}"
        ),
    )
    layout = create_aedt_app(
        Hfss3dLayout,
        args,
        project=project_path,
        design=recipe["design_name"],
        **aedt_constructor_kwargs(args),
    )
    ensure_design_modeler_units(layout, recipe, recipe["type"])
    material_context = load_aedt_material_context(case, package_root)
    ensure_aedt_project_materials(layout, material_context, result_dir, allow_missing=True)
    ok = layout.import_gds(
        input_file=str(package_path(package_root, case["gds"])),
        output_dir=str(aedb_path),
        control_file=str(control_path),
        set_as_active=True,
        close_active_project=False,
    )
    if not ok:
        raise RuntimeError(f"Hfss3dLayout.import_gds failed for case {case['id']}")
    ensure_design_modeler_units(layout, recipe, recipe["type"])
    return layout


def object_names(app):
    names = []
    for attr in ("modeler", "oeditor"):
        target = getattr(app, attr, None)
        if target is None:
            continue
        for name_attr in ("object_names", "objects"):
            value = getattr(target, name_attr, None)
            if value is None:
                continue
            try:
                names.extend(str(item) for item in value)
            except TypeError:
                pass
    return sorted(set(names))


def match_patterns(names, patterns, *, label, min_count=1, exact_count=None):
    matched = sorted(
        {name for pattern in patterns for name in names if fnmatch.fnmatch(name, pattern)}
    )
    if exact_count is not None and len(matched) != exact_count:
        raise RuntimeError(f"{label} expected exactly {exact_count} objects, got {matched}")
    if len(matched) < min_count:
        raise RuntimeError(f"{label} expected at least {min_count} objects, got {matched}")
    return matched


def manifest_hpc_resource(manifest):
    hpc = manifest.get("hpc") or {}
    resource = dict(AEDT_HPC_DEFAULT_RESOURCE)
    resource.update(dict(hpc.get("resource") or {}))
    return resource


def hpc_cli_override_options(args):
    options = (
        ("--num-cores", args.num_cores),
        ("--max-workers", args.max_workers),
        ("--memory-mb-total", args.memory_mb_total),
        ("--memory-mb-per-worker", args.memory_mb_per_worker),
        ("--ram-percent", args.ram_percent),
        ("--core-budget", args.core_budget),
    )
    return [option for option, value in options if value is not None]


def validate_hpc_acf_override_contract(args):
    override_options = hpc_cli_override_options(args)
    if args.acf_file and override_options:
        raise RuntimeError(
            "--acf-file cannot be combined with AEDT HPC resource overrides: "
            f"{', '.join(override_options)}"
        )


def apply_hpc_cli_overrides(resource, args):
    resolved = dict(resource)
    if args.num_cores is not None:
        resolved["num_cores"] = int(args.num_cores)
    if args.max_workers is not None:
        resolved["max_workers"] = int(args.max_workers)
    if args.memory_mb_total is not None:
        resolved["memory_mb_total"] = int(args.memory_mb_total)
    if args.memory_mb_per_worker is not None:
        resolved["memory_mb_per_worker"] = int(args.memory_mb_per_worker)
    if args.ram_percent is not None:
        resolved["ram_percent"] = int(args.ram_percent)
    if args.core_budget is not None:
        resolved["core_budget"] = int(args.core_budget)
    return validate_hpc_resource(resolved)


def validate_hpc_resource(resource):
    int_fields = (
        "num_engines",
        "num_cores",
        "max_workers",
        "num_job_cores",
        "num_gpus",
        "num_variations_to_distribute",
    )
    for field in int_fields:
        resource[field] = int(resource[field])
        if resource[field] < 0:
            raise RuntimeError(f"AEDT HPC resource {field} must be non-negative")
    if resource["num_engines"] < 1 or resource["num_cores"] < 1 or resource["max_workers"] < 1:
        raise RuntimeError("AEDT HPC num_engines, num_cores, and max_workers must be >= 1")
    core_budget = resource.get("core_budget")
    if core_budget is not None:
        resource["core_budget"] = int(core_budget)
        if resource["num_cores"] * resource["max_workers"] > resource["core_budget"]:
            raise RuntimeError(
                "AEDT HPC worker core request exceeds core_budget: "
                f"num_cores={resource['num_cores']}, "
                f"max_workers={resource['max_workers']}, "
                f"core_budget={resource['core_budget']}"
            )
    for field in ("memory_mb_total", "memory_mb_per_worker", "ram_percent"):
        if resource.get(field) is not None:
            resource[field] = int(resource[field])
            if resource[field] < 1:
                raise RuntimeError(f"AEDT HPC resource {field} must be >= 1")
    if resource.get("ram_percent") is not None and resource["ram_percent"] > 100:
        raise RuntimeError("AEDT HPC ram_percent must be <= 100")
    total = resource.get("memory_mb_total")
    per_worker = resource.get("memory_mb_per_worker")
    if (
        total is not None
        and per_worker is not None
        and per_worker * resource["max_workers"] > total
    ):
        raise RuntimeError(
            "AEDT HPC worker memory request exceeds memory_mb_total: "
            f"{per_worker * resource['max_workers']} MB requested, "
            f"memory_mb_total={total}"
        )
    distribution_types = [
        str(item).strip() for item in resource.get("allowed_distribution_types") or []
    ]
    if not distribution_types or any(not item for item in distribution_types):
        raise RuntimeError("AEDT HPC allowed_distribution_types must contain non-empty entries")
    resource["allowed_distribution_types"] = distribution_types
    return resource


def hpc_memory_mb_per_worker(resource):
    if resource.get("memory_mb_per_worker") is not None:
        return int(resource["memory_mb_per_worker"])
    if resource.get("memory_mb_total") is None:
        return None
    return max(1, int(int(resource["memory_mb_total"]) // int(resource["max_workers"])))


def hpc_ram_percent(resource):
    if resource.get("ram_percent") is not None:
        return int(resource["ram_percent"])
    total = resource.get("memory_mb_total")
    per_worker = hpc_memory_mb_per_worker(resource)
    if total is None or per_worker is None:
        return 90
    return max(1, min(100, int(per_worker * 100 / int(total))))


def hpc_resolved_payload(resource):
    return {
        **resource,
        "memory_mb_per_worker_resolved": hpc_memory_mb_per_worker(resource),
        "ram_percent_resolved": hpc_ram_percent(resource),
        "worker_core_total": int(resource["num_cores"]) * int(resource["max_workers"]),
    }


def resolve_runtime_hpc_resource(manifest, args):
    return hpc_resolved_payload(apply_hpc_cli_overrides(manifest_hpc_resource(manifest), args))


def render_hpc_acf(
    resource,
    *,
    config_name="OrPen_Q2D_Local",
    design_type=AEDT_Q2D_HPC_DESIGN_TYPE,
):
    distribution_types = ", ".join(
        f"'{distribution_type}'" for distribution_type in resource["allowed_distribution_types"]
    )
    distribution_count = len(resource["allowed_distribution_types"])
    return f"""$begin 'Configs'
\t$begin 'Configs'
\t\t$begin 'DSOConfig'
\t\t\tConfigName='{config_name}'
\t\t\tDesignType='{design_type}'
\t\t\t$begin 'DSOMachineList'
\t\t\t\t$begin 'DSOMachineInfo'
\t\t\t\t\tMachineName='{resource.get("machine_name", "localhost")}'
\t\t\t\t\tNumEngines={resource["num_engines"]}
\t\t\t\t\tNumCores={resource["num_cores"]}
\t\t\t\t\tIsEnabled=true
\t\t\t\t\tRAMPercent={hpc_ram_percent(resource)}
\t\t\t\t\tNumJobCores={resource.get("num_job_cores", 0)}
\t\t\t\t\tNumGPUs={resource.get("num_gpus", 0)}
\t\t\t\t$end 'DSOMachineInfo'
\t\t\t$end 'DSOMachineList'
\t\t\tUseAutoSettings={str(bool(resource.get("use_auto_settings", True))).lower()}
\t\t\tNumVariationsToDistribute={resource.get("num_variations_to_distribute", 1)}
\t\t\t$begin 'DSOJobDistributionInfo'
\t\t\t\tAllowedDistributionTypes[{distribution_count}: {distribution_types}]
\t\t\t\tEnable2LevelDistribution=false
\t\t\t\tNumL1Engines=0
\t\t\t\tUseDefaultsForDistributionTypes=false
\t\t\t\tContext()
\t\t\t$end 'DSOJobDistributionInfo'
\t\t\t$begin 'DSOMachineOptionsInfo'
\t\t\t\tMenuValues()
\t\t\t\tIntValues()
\t\t\t\tBoolValues()
\t\t\t\tDoubleValues()
\t\t\t$end 'DSOMachineOptionsInfo'
\t\t$end 'DSOConfig'
\t$end 'Configs'
$end 'Configs'
"""


def resolve_runtime_acf_file(args, manifest, package_root, log_root):
    validate_hpc_acf_override_contract(args)
    if args.acf_file:
        acf_path = Path(args.acf_file)
        if not acf_path.is_absolute():
            acf_path = (Path.cwd() / acf_path).resolve()
        return acf_path
    hpc = manifest.get("hpc") or {}
    resource = apply_hpc_cli_overrides(manifest_hpc_resource(manifest), args)
    has_cli_override = bool(hpc_cli_override_options(args))
    if not has_cli_override and hpc.get("acf_file"):
        return package_path(package_root, hpc["acf_file"])
    acf_path = Path(log_root) / "hpc" / "q2d_runtime.acf"
    write_runtime_hpc_artifacts(acf_path, resource)
    return acf_path


def write_runtime_hpc_artifacts(acf_path, resource):
    acf_path = Path(acf_path)
    acf_path.parent.mkdir(parents=True, exist_ok=True)
    acf_path.write_text(render_hpc_acf(resource), encoding="utf-8")
    write_json(
        acf_path.with_name("aedt_hpc_runtime_profile.json"),
        {
            "schema_version": "aedt-hpc-profile.v1",
            "profile": resource.get("profile_name", "aedt-q2d-local"),
            "acf_file": str(acf_path),
            "acf_design_type": AEDT_Q2D_HPC_DESIGN_TYPE,
            "project_concurrency": "isolated_worker_projects",
            "resource": hpc_resolved_payload(resource),
        },
    )


def q2d_analyze_setup_kwargs(args, manifest, package_root, log_root):
    acf_path = resolve_runtime_acf_file(args, manifest, package_root, log_root)
    if acf_path is None:
        return {}, {}
    payload = {
        "acf_file": str(acf_path),
        "resource": hpc_resolved_payload(
            apply_hpc_cli_overrides(manifest_hpc_resource(manifest), args)
        ),
    }
    return {"acf_file": str(acf_path)}, payload


def elapsed_stage_record(stage, started_at, **payload):
    record = {
        "stage": stage,
        "elapsed_seconds": time.monotonic() - started_at,
    }
    record.update(payload)
    return record


def timed_stage(stage_timing, stage, func, *args, **kwargs):
    started_at = time.monotonic()
    try:
        result = func(*args, **kwargs)
    except Exception as exc:
        stage_timing.append(
            elapsed_stage_record(stage, started_at, return_value=False, error=str(exc))
        )
        raise
    stage_timing.append(elapsed_stage_record(stage, started_at, return_value=bool(result)))
    return result


class AedtBlockingStageHeartbeat:
    def __init__(
        self,
        log_dir,
        stage,
        *,
        project_path=None,
        extra_paths=None,
        interval_seconds=None,
        metadata=None,
    ):
        self.log_dir = Path(log_dir)
        self.stage = str(stage)
        self.project_path = None if project_path is None else Path(project_path)
        self.extra_paths = {str(key): Path(value) for key, value in (extra_paths or {}).items()}
        self.interval_seconds = float(
            interval_seconds
            if interval_seconds is not None
            else os.environ.get("AEDT_PROGRESS_INTERVAL_SECONDS", "30")
        )
        self.metadata = dict(metadata or {})
        self.started_at = None
        self._stop = threading.Event()
        self._thread = None

    def __enter__(self):
        self.started_at = time.monotonic()
        self._write("started")
        self._thread = threading.Thread(
            target=self._run,
            name=f"aedt-progress-{self.stage}",
            daemon=True,
        )
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, _traceback):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._write("failed" if exc is not None else "finished", error=str(exc) if exc else None)
        return False

    def _run(self):
        while not self._stop.wait(max(self.interval_seconds, 0.1)):
            self._write("heartbeat")

    def _write(self, event, *, error=None):
        payload = {
            "event": event,
            "stage": self.stage,
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "elapsed_seconds": 0.0
            if self.started_at is None
            else time.monotonic() - self.started_at,
            "pid": os.getpid(),
            "metadata": self.metadata,
        }
        if error is not None:
            payload["error"] = error
        if self.project_path is not None:
            payload["project"] = file_status_record(self.project_path)
            payload["project_lock"] = file_status_record(Path(str(self.project_path) + ".lock"))
            payload["project_auto"] = file_status_record(Path(str(self.project_path) + ".auto"))
        if self.extra_paths:
            payload["paths"] = {
                label: file_status_record(path) for label, path in self.extra_paths.items()
            }
        append_jsonl(self.log_dir / "progress.jsonl", payload)


def file_status_record(path):
    path = Path(path)
    record = {"path": str(path), "exists": path.exists()}
    if not record["exists"]:
        return record
    try:
        stat = path.stat()
    except OSError as exc:
        record["error"] = str(exc)
        return record
    record["size"] = stat.st_size
    record["mtime_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stat.st_mtime))
    return record


def aedt_blocking_stage_heartbeat(log_dir, stage, **kwargs):
    return AedtBlockingStageHeartbeat(log_dir, stage, **kwargs)


def file_export_record(path, *, artifact_family, artifact_type=None, problem_type=None):
    path = Path(path)
    return {
        "artifact_family": artifact_family,
        "artifact_type": artifact_type,
        "problem_type": problem_type,
        "file_name": str(path),
        "return_value": path.is_file() and path.stat().st_size > 0,
        "file_size": path.stat().st_size if path.is_file() else None,
    }


def scan_exported_files(
    result_dir,
    patterns,
    *,
    artifact_family,
    artifact_type=None,
    problem_type=None,
):
    records = []
    for pattern in patterns:
        for path in sorted(Path(result_dir).glob(pattern)):
            records.append(
                file_export_record(
                    path,
                    artifact_family=artifact_family,
                    artifact_type=artifact_type,
                    problem_type=problem_type,
                )
            )
    unique = {}
    for record in records:
        unique[record["file_name"]] = record
    return sorted(unique.values(), key=lambda item: item["file_name"])


def export_aedt_benchmark_artifacts(
    app,
    setup,
    result_dir,
    *,
    solver_type,
    problem_types,
    stage_timing,
):
    result_dir = Path(result_dir)
    exports = []
    started_at = time.monotonic()
    try:
        app.export_profile(setup=setup, output_file=str(result_dir / "aedt_profile.prof"))
        stage_timing.append(elapsed_stage_record("export_profile", started_at, return_value=True))
    except Exception as exc:
        stage_timing.append(
            elapsed_stage_record(
                "export_profile",
                started_at,
                return_value=False,
                error=str(exc),
            )
        )
        exports.append(
            {
                "artifact_family": "profile",
                "artifact_type": "prof",
                "return_value": False,
                "error": str(exc),
            }
        )
    exports.extend(
        scan_exported_files(
            result_dir,
            ("aedt_profile*.prof",),
            artifact_family="profile",
            artifact_type="prof",
        )
    )

    started_at = time.monotonic()
    try:
        app.export_convergence(setup=setup, output_file=str(result_dir / "aedt_convergence.prop"))
        stage_timing.append(
            elapsed_stage_record("export_convergence", started_at, return_value=True)
        )
    except Exception as exc:
        stage_timing.append(
            elapsed_stage_record(
                "export_convergence",
                started_at,
                return_value=False,
                error=str(exc),
            )
        )
        exports.append(
            {
                "artifact_family": "convergence",
                "artifact_type": "prop",
                "return_value": False,
                "error": str(exc),
            }
        )
    exports.extend(
        scan_exported_files(
            result_dir,
            ("aedt_convergence*.prop", "aedt_convergence*.csv"),
            artifact_family="convergence",
            artifact_type="prop",
        )
    )

    mesh_setup_types = aedt_mesh_setup_types(solver_type, problem_types)
    for setup_type in mesh_setup_types:
        safe_type = str(setup_type).lower().replace(" ", "_")
        mesh_path = result_dir / f"aedt_mesh_stats_{safe_type}.ms"
        started_at = time.monotonic()
        try:
            if solver_type in {"q2d_extraction", "q3d_extraction", "q2d", "q3d"}:
                app.export_mesh_stats(setup=setup, output_file=mesh_path, setup_type=setup_type)
            else:
                app.export_mesh_stats(setup=setup, output_file=str(mesh_path))
            stage_timing.append(
                elapsed_stage_record(
                    f"export_mesh_stats_{safe_type}",
                    started_at,
                    return_value=mesh_path.is_file(),
                )
            )
        except Exception as exc:
            stage_timing.append(
                elapsed_stage_record(
                    f"export_mesh_stats_{safe_type}",
                    started_at,
                    return_value=False,
                    error=str(exc),
                )
            )
            exports.append(
                {
                    "artifact_family": "mesh_stats",
                    "artifact_type": "ms",
                    "problem_type": setup_type,
                    "file_name": str(mesh_path),
                    "return_value": False,
                    "error": str(exc),
                }
            )
            continue
        exports.append(
            file_export_record(
                mesh_path,
                artifact_family="mesh_stats",
                artifact_type="ms",
                problem_type=setup_type,
            )
        )
    return exports


def aedt_mesh_setup_types(solver_type, problem_types):
    solver = str(solver_type)
    if solver in {"q2d_extraction", "q2d"}:
        return [str(item) for item in problem_types or ("CG", "RL")]
    if solver in {"q3d_extraction", "q3d"}:
        setup_types = []
        for item in problem_types or ("CG",):
            text = str(item)
            if text == "C":
                setup_types.append("CG")
            else:
                setup_types.append(text)
        return setup_types
    return [None]


def parse_aedt_frequency_expression(value):
    text = str(value or "").strip()
    match = re.fullmatch(
        r"([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?)\s*([A-Za-z]+)",
        text,
    )
    if not match:
        return {"expression": text, "value": None, "unit": None}
    return {"expression": text, "value": match.group(1), "unit": match.group(2)}


def q2d_matrix_frequency_export_kwargs(frequency_expression):
    frequency = parse_aedt_frequency_expression(frequency_expression)
    if frequency_expression is None:
        return frequency, {}
    if not frequency["value"] or not frequency["unit"]:
        raise RuntimeError(
            "Q2D matrix export adaptive_frequency must be a numeric value with unit, "
            f"for example '6GHz'; got {frequency_expression!r}."
        )
    unit_key = str(frequency["unit"]).lower()
    scale = AEDT_FREQUENCY_UNIT_TO_HZ.get(unit_key)
    if scale is None:
        raise RuntimeError(
            "Q2D matrix export adaptive_frequency has unsupported unit "
            f"{frequency['unit']!r}; supported units are Hz, kHz, MHz, GHz, and THz."
        )
    frequency_hz = Decimal(str(frequency["value"])) * scale
    frequency["value_hz"] = format(frequency_hz.normalize(), "f")
    return frequency, {
        "freq": frequency["value"],
        "freq_unit": frequency["unit"],
        "freq_hz": frequency["value_hz"],
    }


def aedt_nominal_variation_string(app):
    try:
        nominal_values = app.available_variations.nominal_variation(dependent_params=False)
    except Exception:
        try:
            return str(app.odesign.GetNominalVariation() or "")
        except Exception:
            return ""
    if not nominal_values:
        return ""
    variations = []
    for key, value in nominal_values.items():
        variations.append(f"{key}='{value}'")
    return ",".join(variations)


def q2d_matrix_analysis_setup(app, setup, sweep):
    resolved_sweep = sweep
    if resolved_sweep is None:
        try:
            resolved_sweep = app.design_solutions.default_adaptive
        except KeyError:
            resolved_sweep = "LastAdaptive"
    return f"{setup} : {str(resolved_sweep).replace(' ', '')}", resolved_sweep


def export_q2d_matrix_data_direct(
    app,
    file_name,
    *,
    problem_type,
    matrix_type,
    setup,
    sweep,
    frequency_hz,
):
    analysis_setup, resolved_sweep = q2d_matrix_analysis_setup(app, setup, sweep)
    details = {
        "direct_odesign_export": True,
        "analysis_setup": analysis_setup,
        "resolved_sweep": resolved_sweep,
        "aedt_export_frequency_hz": frequency_hz,
    }
    try:
        app.odesign.ExportMatrixData(
            str(file_name),
            problem_type,
            aedt_nominal_variation_string(app),
            analysis_setup,
            "Original",
            "ohm",
            "nH",
            "pF",
            "mho",
            frequency_hz,
            "Distributed",
            "1meter",
            matrix_type,
            0,
            15,
            20,
            1,
        )
    except Exception as exc:
        details["error"] = str(exc)
        return False, details
    return True, details


def q2d_adaptive_frequency(recipe):
    settings = recipe.get("q2d_setup", {}) or {}
    return str(settings.get("adaptive_frequency") or "6GHz")


def q2d_existing_adaptive_sweeps(app, setup):
    sweeps = []
    for item in getattr(app, "existing_analysis_sweeps", []) or []:
        text = str(item)
        if " : " in text:
            item_setup, sweep = text.split(" : ", 1)
            if item_setup.strip() != setup:
                continue
        else:
            sweep = text
        normalized = sweep.strip()
        if normalized and normalized != "LastAdaptive" and "adaptive" in normalized.lower():
            sweeps.append(normalized)
    return sorted(set(sweeps))


def export_q2d_physical_convergence(app, recipe, result_dir):
    setup = recipe.get("setup_name", "Setup1")
    convergence_dir = Path(result_dir) / "q2d_physical_convergence"
    convergence_dir.mkdir(parents=True, exist_ok=True)
    exports = []
    sweeps = q2d_existing_adaptive_sweeps(app, setup)
    if not sweeps:
        return {
            "status": "missing_source",
            "reason": (
                "No adaptive pass sweeps were available from PyAEDT existing_analysis_sweeps."
            ),
            "exports": exports,
        }
    for sweep in sweeps:
        pass_match = re.search(r"(\d+)", sweep)
        pass_label = f"pass_{pass_match.group(1)}" if pass_match else safe_filename(sweep)
        for problem_type in recipe.get("matrix_problem_types", ("CG", "RL")):
            pyaedt_problem_type = q2d_pyaedt_problem_type(problem_type)
            try:
                exports.append(
                    export_matrix_data_checked(
                        app,
                        convergence_dir,
                        setup=setup,
                        requested_problem_type=problem_type,
                        pyaedt_problem_type=pyaedt_problem_type,
                        matrix_type="Maxwell",
                        sweep=sweep,
                        file_prefix=pass_label,
                        frequency_expression=q2d_adaptive_frequency(recipe),
                    )
                )
            except Exception as exc:
                exports.append(
                    {
                        "requested_problem_type": problem_type,
                        "pyaedt_problem_type": pyaedt_problem_type,
                        "matrix_type": "Maxwell",
                        "sweep": sweep,
                        "return_value": False,
                        "error": str(exc),
                    }
                )
    return {"status": "created", "sweeps": sweeps, "exports": exports}


def safe_filename(value):
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value)).strip("._")
    return text or "value"


def q2d_source_hashes(case, package_root):
    keys = (
        "gds",
        "layer_mapping_json",
        "aedt_material_context",
        "q2d_conductors",
        "q2d_cross_section",
    )
    return {
        key: file_sha256(package_path(package_root, case[key])) for key in keys if case.get(key)
    }


def q2d_geometry_mode(recipe):
    mode = str(recipe.get("q2d_geometry_mode") or "hfss_section")
    if mode not in {"hfss_section", "semantic_cross_section"}:
        raise RuntimeError(f"Unsupported Q2D geometry mode: {mode!r}")
    return mode


def q2d_geometry_settings(recipe):
    return {
        "q2d_geometry_mode": q2d_geometry_mode(recipe),
        "section_plane": recipe.get("section_plane", "XY"),
        "rotations": recipe.get("rotations", []),
        "modeler_units": recipe_modeler_units(recipe),
    }


def q2d_recipe_settings(recipe):
    return {
        "geometry": q2d_geometry_settings(recipe),
        "q2d_setup": recipe.get("q2d_setup", {}),
        "q2d_region": recipe.get("q2d_region", {}),
        "material_policy": recipe.get("material_policy", {}),
        "assignment_source": recipe.get("assignment_source"),
        "matrix_problem_types": recipe.get("matrix_problem_types", []),
        "matrix_types": recipe.get("matrix_types", []),
    }


def stage_record(stage, status, **payload):
    record = {"stage": stage, "status": status}
    record.update(payload)
    return record


def write_q2d_stage_outputs(log_dir, detection, workflow_state):
    write_json(log_dir / "q2d_stage_detection.json", detection)
    write_json(log_dir / "q2d_workflow_state.json", workflow_state)


def load_q2d_conductor_rows(case, package_root):
    relative = case.get("q2d_conductors")
    if not relative:
        raise RuntimeError(f"Case {case['id']} has no q2d_conductors sidecar")
    path = package_path(package_root, relative)
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("conductors") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise RuntimeError(f"Q2D conductor sidecar must contain conductor rows: {path}")
    return rows


def q2d_conductor_groups(rows):
    supported_types = {
        "Signal Line",
        "Reference Ground",
        "Non Ideal Ground",
        "Floating Line",
        "Surface Ground",
    }
    marker_names = set()
    assignment_types = {}
    groups = {}
    for row in rows:
        marker_name = str(row.get("name") or "").strip()
        conductor_type = str(row.get("conductor_type") or "").strip()
        assignment_name = str(row.get("assignment_name") or "").strip()
        if not marker_name:
            raise RuntimeError("Q2D conductor sidecar rows require marker name")
        if marker_name in marker_names:
            raise RuntimeError(f"Duplicate Q2D conductor marker name: {marker_name!r}")
        marker_names.add(marker_name)
        if conductor_type not in supported_types:
            raise RuntimeError(f"Invalid Q2D conductor_type: {conductor_type!r}")
        if conductor_type == "Reference Ground" and not assignment_name:
            assignment_name = "Ground"
        if not assignment_name:
            raise RuntimeError(
                "Q2D conductor sidecar rows require assignment_name except Reference Ground"
            )
        previous_type = assignment_types.get(assignment_name)
        if previous_type is not None and previous_type != conductor_type:
            raise RuntimeError(
                f"Q2D assignment_name {assignment_name!r} is used with both "
                f"{previous_type!r} and {conductor_type!r}"
            )
        assignment_types[assignment_name] = conductor_type
        group = groups.setdefault(
            assignment_name,
            {"assignment_name": assignment_name, "conductor_type": conductor_type, "markers": []},
        )
        group["markers"].append(row)

    conductor_types = {group["conductor_type"] for group in groups.values()}
    if "Signal Line" not in conductor_types:
        raise RuntimeError("Q2D conductor sidecar requires at least one Signal Line assignment")
    if "Reference Ground" not in conductor_types:
        raise RuntimeError(
            "Q2D conductor sidecar requires at least one Reference Ground assignment"
        )
    return sorted(groups.values(), key=lambda group: group["assignment_name"])


def load_q2d_semantic_cross_section(case, package_root):
    relative = case.get("q2d_cross_section")
    if not relative:
        raise RuntimeError(f"Case {case['id']} has no q2d_cross_section sidecar")
    payload = read_json(package_path(package_root, relative))
    return validate_runtime_q2d_cross_section_payload(payload, relative)


def validate_runtime_q2d_cross_section_payload(payload, source):
    if not isinstance(payload, dict):
        raise RuntimeError(f"Q2D semantic cross-section must be a JSON object: {source}")
    if payload.get("schema_version") != "q2d-semantic-cross-section.v1":
        raise RuntimeError(f"Q2D semantic cross-section has unsupported schema: {source}")
    stack = payload.get("stack")
    face_patterns = payload.get("face_patterns")
    if not isinstance(stack, list) or not stack:
        raise RuntimeError(f"Q2D semantic cross-section requires stack: {source}")
    if not isinstance(face_patterns, list) or not face_patterns:
        raise RuntimeError(f"Q2D semantic cross-section requires face_patterns: {source}")
    die_ids = []
    for index, element in enumerate(stack):
        if not isinstance(element, dict):
            raise RuntimeError(f"Q2D stack[{index}] must be an object: {source}")
        kind = element.get("kind")
        if kind == "die":
            die_ids.append(_q2d_semantic_text(element.get("id"), f"stack[{index}].id"))
            _q2d_semantic_positive(element.get("thickness_um"), f"stack[{index}].thickness_um")
            _q2d_semantic_text(element.get("material"), f"stack[{index}].material")
        elif kind in {"air", "die_gap"}:
            if kind == "air" and index not in {0, len(stack) - 1}:
                raise RuntimeError(f"Q2D Air is only allowed at stack edges: {source}")
            _q2d_semantic_positive(element.get("height_um"), f"stack[{index}].height_um")
        else:
            raise RuntimeError(f"Unsupported Q2D stack element kind {kind!r}: {source}")
    if not die_ids:
        raise RuntimeError(f"Q2D semantic cross-section requires at least one die: {source}")
    duplicates = sorted({die_id for die_id in die_ids if die_ids.count(die_id) > 1})
    if duplicates:
        raise RuntimeError(f"Duplicate Q2D semantic die ids {duplicates}: {source}")
    known_die_ids = set(die_ids)
    has_trace = False
    for pattern_index, pattern in enumerate(face_patterns):
        if not isinstance(pattern, dict):
            raise RuntimeError(f"Q2D face_patterns[{pattern_index}] must be an object: {source}")
        die = _q2d_semantic_text(pattern.get("die"), f"face_patterns[{pattern_index}].die")
        if die not in known_die_ids:
            raise RuntimeError(f"Q2D face pattern references unknown die {die!r}: {source}")
        if pattern.get("face") not in {"top", "bottom"}:
            raise RuntimeError(f"Q2D face must be top or bottom: {source}")
        _q2d_semantic_positive(
            pattern.get("metal_thickness_um"),
            f"face_patterns[{pattern_index}].metal_thickness_um",
        )
        segments = pattern.get("segments")
        if not isinstance(segments, list) or not segments:
            raise RuntimeError(f"Q2D face pattern requires segments: {source}")
        for segment_index, segment in enumerate(segments):
            if not isinstance(segment, dict):
                raise RuntimeError(
                    f"Q2D face_patterns[{pattern_index}].segments[{segment_index}] "
                    f"must be an object: {source}"
                )
            kind = segment.get("kind")
            if kind in {"ground", "gap"}:
                _q2d_semantic_positive(
                    segment.get("width_um"),
                    f"face_patterns[{pattern_index}].segments[{segment_index}].width_um",
                )
            elif kind == "trace":
                has_trace = True
                _q2d_semantic_text(
                    segment.get("name"),
                    f"face_patterns[{pattern_index}].segments[{segment_index}].name",
                )
                _q2d_semantic_positive(
                    segment.get("width_um"),
                    f"face_patterns[{pattern_index}].segments[{segment_index}].width_um",
                )
            else:
                raise RuntimeError(f"Unsupported Q2D face segment kind {kind!r}: {source}")
    if not has_trace:
        raise RuntimeError(f"Q2D semantic cross-section requires at least one trace: {source}")
    return payload


def q2d_semantic_geometry_plan(payload):
    stack = payload["stack"]
    bottom_air_um = 0.0
    top_air_um = 0.0
    y_cursor = 0.0
    die_spans = {}
    die_order = []
    for index, element in enumerate(stack):
        kind = element["kind"]
        if kind == "air":
            if index == 0:
                bottom_air_um = float(element["height_um"])
            elif index == len(stack) - 1:
                top_air_um = float(element["height_um"])
            continue
        if kind == "die_gap":
            y_cursor += float(element["height_um"])
            continue
        die_id = str(element["id"])
        thickness_um = float(element["thickness_um"])
        die_spans[die_id] = {
            "id": die_id,
            "y_min_um": y_cursor,
            "y_max_um": y_cursor + thickness_um,
            "thickness_um": thickness_um,
            "material": str(element["material"]),
        }
        die_order.append(die_id)
        y_cursor += thickness_um

    pattern_extents = []
    for pattern in payload["face_patterns"]:
        x0_um = float(pattern.get("x0_um", 0.0))
        x1_um = x0_um + sum(float(segment["width_um"]) for segment in pattern["segments"])
        pattern_extents.append((x0_um, x1_um))
    x_min_um = min(extent[0] for extent in pattern_extents)
    x_max_um = max(extent[1] for extent in pattern_extents)
    if x_max_um <= x_min_um:
        raise RuntimeError("Q2D semantic cross-section has empty lateral extent")

    rectangles = []
    for die_id in die_order:
        span = die_spans[die_id]
        rectangles.append(
            {
                "name": f"q2d_die_{safe_filename(die_id)}",
                "kind": "dielectric",
                "die": die_id,
                "face": None,
                "assignment_name": None,
                "conductor_type": None,
                "material": normalize_aedt_material(span["material"]),
                "origin_um": [x_min_um, span["y_min_um"]],
                "sizes_um": [x_max_um - x_min_um, span["thickness_um"]],
            }
        )

    assignments = {}
    for pattern_index, pattern in enumerate(payload["face_patterns"]):
        die_id = str(pattern["die"])
        span = die_spans[die_id]
        face = str(pattern["face"])
        metal_thickness_um = float(pattern["metal_thickness_um"])
        y0_um = span["y_max_um"] if face == "top" else span["y_min_um"] - metal_thickness_um
        x_cursor = float(pattern.get("x0_um", 0.0))
        for segment_index, segment in enumerate(pattern["segments"]):
            width_um = float(segment["width_um"])
            kind = str(segment["kind"])
            if kind == "gap":
                x_cursor += width_um
                continue
            if kind == "ground":
                assignment_name = str(pattern.get("ground_assignment_name") or "Ground")
                conductor_type = "Reference Ground"
                object_label = "ground"
            else:
                assignment_name = str(segment["name"])
                conductor_type = "Signal Line"
                object_label = f"trace_{safe_filename(assignment_name)}"
            object_name = (
                f"q2d_fp{pattern_index:02d}_{safe_filename(die_id)}_{face}_"
                f"{segment_index:02d}_{object_label}"
            )
            rectangles.append(
                {
                    "name": object_name,
                    "kind": "conductor",
                    "die": die_id,
                    "face": face,
                    "assignment_name": assignment_name,
                    "conductor_type": conductor_type,
                    "material": normalize_aedt_material(pattern.get("material") or "pec"),
                    "origin_um": [x_cursor, y0_um],
                    "sizes_um": [width_um, metal_thickness_um],
                }
            )
            assignment = assignments.setdefault(
                assignment_name,
                {
                    "assignment_name": assignment_name,
                    "conductor_type": conductor_type,
                    "objects": [],
                },
            )
            if assignment["conductor_type"] != conductor_type:
                raise RuntimeError(
                    f"Q2D assignment {assignment_name!r} is both "
                    f"{assignment['conductor_type']!r} and {conductor_type!r}"
                )
            assignment["objects"].append(object_name)
            x_cursor += width_um

    return {
        "schema_version": "q2d-semantic-runtime-plan.v1",
        "region": payload.get("region") or {},
        "x_extent_um": {"min": x_min_um, "max": x_max_um, "width": x_max_um - x_min_um},
        "stack_height_um": y_cursor,
        "die_spans": die_spans,
        "region_padding_um": {
            "+X": None,
            "-X": None,
            "+Y": top_air_um,
            "-Y": bottom_air_um,
        },
        "rectangles": rectangles,
        "assignments": dict(sorted(assignments.items())),
    }


def _q2d_semantic_text(value, label):
    text = str(value or "").strip()
    if not text:
        raise RuntimeError(f"Q2D semantic {label} must not be empty")
    return text


def _q2d_semantic_positive(value, label):
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"Q2D semantic {label} must be numeric") from exc
    if number <= 0.0:
        raise RuntimeError(f"Q2D semantic {label} must be positive")
    return number


def create_layout_setup(layout, recipe):
    setup = layout.create_setup(
        name=recipe.get("setup_name", "Setup1"),
        **recipe.get("setup_options", {}),
    )
    sweep = recipe.get("frequency_sweep") or {}
    if sweep:
        layout.create_linear_step_sweep(setup=setup.name, **sweep)
    return setup


@recipe_handler("hfss_driven_terminal")
def run_hfss_driven_terminal(case, recipe, manifest, package_root, result_dir, log_dir, args):
    layout = import_gds_layout(case, recipe, manifest, package_root, result_dir, log_dir, args)
    setup = create_layout_setup(layout, recipe)
    names = object_names(layout)
    terminal_matches = []
    port_matches = []
    if recipe.get("terminal_patterns"):
        terminal_matches = match_patterns(
            names,
            recipe["terminal_patterns"],
            label="HFSS terminal patterns",
            min_count=1,
        )
    if recipe.get("port_patterns"):
        port_matches = match_patterns(
            names,
            recipe["port_patterns"],
            label="HFSS port patterns",
            min_count=1,
        )
    solve_status = {
        "mode": args.mode,
        "analyze_setup": None,
        "benchmark_exports": [],
        "stage_timing": [],
    }
    if args.mode == "solve":
        stage_timing = solve_status["stage_timing"]
        analyze_ok = timed_stage(stage_timing, "analyze_setup", layout.analyze_setup, setup.name)
        solve_status["analyze_setup"] = {"setup": setup.name, "return_value": bool(analyze_ok)}
        started_at = time.monotonic()
        exported_results = layout.export_results(export_folder=str(result_dir))
        stage_timing.append(
            elapsed_stage_record(
                "export_results",
                started_at,
                return_value=bool(exported_results),
                exported_files=[str(path) for path in exported_results or []],
            )
        )
        solve_status["benchmark_exports"] = export_aedt_benchmark_artifacts(
            layout,
            setup.name,
            result_dir,
            solver_type=recipe["type"],
            problem_types=recipe.get("matrix_problem_types", ()),
            stage_timing=stage_timing,
        )
        write_json(result_dir / "solve_timing.json", {"stage_timing": stage_timing})
    write_json(
        result_dir / "simulation_metadata.json",
        {
            "recipe_type": recipe["type"],
            "setup": setup.name,
            "terminal_matches": terminal_matches,
            "port_matches": port_matches,
            "solve_status": solve_status,
        },
    )
    layout.save_project()


@recipe_handler("hfss_eigenmode")
def run_hfss_eigenmode(case, recipe, manifest, package_root, result_dir, log_dir, args):
    layout = import_gds_layout(case, recipe, manifest, package_root, result_dir, log_dir, args)
    setup = create_layout_setup(layout, recipe)
    if recipe.get("mode_count") is not None:
        setup.props["Modes"] = int(recipe["mode_count"])
        setup.update()
    solve_status = {
        "mode": args.mode,
        "analyze_setup": None,
        "benchmark_exports": [],
        "stage_timing": [],
    }
    if args.mode == "solve":
        stage_timing = solve_status["stage_timing"]
        analyze_ok = timed_stage(stage_timing, "analyze_setup", layout.analyze_setup, setup.name)
        solve_status["analyze_setup"] = {"setup": setup.name, "return_value": bool(analyze_ok)}
        solve_status["benchmark_exports"] = export_aedt_benchmark_artifacts(
            layout,
            setup.name,
            result_dir,
            solver_type=recipe["type"],
            problem_types=recipe.get("matrix_problem_types", ()),
            stage_timing=stage_timing,
        )
        write_json(result_dir / "solve_timing.json", {"stage_timing": stage_timing})
    write_json(
        result_dir / "simulation_metadata.json",
        {
            "recipe_type": recipe["type"],
            "setup": setup.name,
            "mode_count": recipe.get("mode_count"),
            "solve_status": solve_status,
        },
    )
    layout.save_project()


@recipe_handler("q3d_extraction")
def run_q3d_extraction(case, recipe, manifest, package_root, result_dir, log_dir, args):
    layout = import_gds_layout(case, recipe, manifest, package_root, result_dir, log_dir, args)
    setup = create_layout_setup(layout, recipe)
    export_file = result_dir / f"{case['id']}_{recipe['id']}.q3d"
    try:
        setup.export_to_q3d(str(export_file), keep_net_name=True, unite=True)
    except AttributeError:
        log(log_dir, "Setup3DLayout.export_to_q3d is unavailable in this PyAEDT version.")

    from ansys.aedt.core import Q3d

    q3d = create_aedt_app(
        Q3d,
        args,
        project=manifest["project"]["path"],
        design=recipe["design_name"],
        **aedt_constructor_kwargs(args, new_desktop=False),
    )
    ensure_design_modeler_units(q3d, recipe, recipe["type"])
    material_context = load_aedt_material_context(case, package_root)
    ensure_aedt_project_materials(q3d, material_context, result_dir)
    names = object_names(q3d)
    source_matches = []
    if recipe.get("source_patterns"):
        source_matches = match_patterns(
            names,
            recipe["source_patterns"],
            label="Q3D source patterns",
            min_count=1,
        )
    solve_status = {
        "mode": args.mode,
        "analyze_setup": None,
        "matrix_exports": [],
        "benchmark_exports": [],
        "stage_timing": [],
    }
    if args.mode == "solve":
        stage_timing = solve_status["stage_timing"]
        setup_name = recipe.get("setup_name", "Setup1")
        analyze_ok = timed_stage(stage_timing, "analyze_setup", q3d.analyze_setup, setup_name)
        solve_status["analyze_setup"] = {"setup": setup_name, "return_value": bool(analyze_ok)}
        matrix_exports = timed_stage(
            stage_timing,
            "export_q3d_matrices",
            export_q3d_matrices,
            q3d,
            recipe,
            result_dir,
        )
        solve_status["matrix_exports"] = matrix_exports
        solve_status["benchmark_exports"] = export_aedt_benchmark_artifacts(
            q3d,
            setup_name,
            result_dir,
            solver_type=recipe["type"],
            problem_types=recipe.get("matrix_problem_types", ("C", "AC RL")),
            stage_timing=stage_timing,
        )
        write_json(result_dir / "solve_timing.json", {"stage_timing": stage_timing})
    write_json(
        result_dir / "assignment_summary.json",
        {"recipe_type": recipe["type"], "source_matches": source_matches},
    )
    write_json(
        result_dir / "simulation_metadata.json",
        {
            "recipe_type": recipe["type"],
            "setup": recipe.get("setup_name", "Setup1"),
            "solve_status": solve_status,
        },
    )
    q3d.save_project()


@recipe_handler("q2d_extraction")
def run_q2d_extraction(case, recipe, manifest, package_root, result_dir, log_dir, args):
    run_q2d_incremental_workflow(case, recipe, manifest, package_root, result_dir, log_dir, args)


def run_q2d_incremental_workflow(case, recipe, manifest, package_root, result_dir, log_dir, args):
    assignment_source = recipe.get("assignment_source") or "object_patterns"
    geometry_mode = q2d_geometry_mode(recipe)
    material_context = (
        load_aedt_material_context(case, package_root) if case.get("aedt_material_context") else {}
    )
    source_hashes = q2d_source_hashes(case, package_root)
    geometry_settings_hash = sha256_text(stable_json(q2d_geometry_settings(recipe)))
    recipe_settings_hash = sha256_text(stable_json(q2d_recipe_settings(recipe)))
    previous_state = read_json(log_dir / "q2d_workflow_state.json") or {}
    adopted_existing = not bool(previous_state)
    detection = {
        "case_id": case["id"],
        "recipe_id": recipe["id"],
        "mode": args.mode,
        "force_rebuild": args.force_rebuild,
        "stages": [],
    }
    exported_files = []
    workflow_state = {
        "case_id": case["id"],
        "recipe_id": recipe["id"],
        "recipe_type": recipe["type"],
        "mode": args.mode,
        "force_rebuild": args.force_rebuild,
        "adopted_existing": adopted_existing,
        "q2d_geometry_mode": geometry_mode,
        "source_hashes": source_hashes,
        "geometry_settings_hash": geometry_settings_hash,
        "recipe_settings_hash": recipe_settings_hash,
        "hfss_staging_design": (
            f"{recipe['design_name']}_hfss_staging" if geometry_mode == "hfss_section" else None
        ),
        "q2d_design": recipe["design_name"],
        "setup": recipe.get("setup_name", "Setup1"),
        "stage_decisions": [],
        "exported_files": exported_files,
    }
    try:
        validate_previous_q2d_state(
            previous_state,
            source_hashes,
            geometry_settings_hash,
            recipe_settings_hash,
            args,
            detection,
        )
        hfss = None
        imported_objects = []
        section_objects = []
        q2d_section_objects = []
        semantic_geometry_plan = None
        if geometry_mode == "semantic_cross_section":
            q2d, q2d_section_objects, semantic_geometry_plan, record = (
                ensure_q2d_semantic_cross_section_geometry(
                    case,
                    recipe,
                    manifest,
                    package_root,
                    result_dir,
                    args,
                    material_context,
                )
            )
            detection["stages"].append(record)
        else:
            hfss, imported_objects, mapping_payload, record = ensure_q2d_staging_hfss(
                case,
                recipe,
                manifest,
                package_root,
                result_dir,
                log_dir,
                args,
                material_context,
            )
            detection["stages"].append(record)
            section_objects, record = ensure_q2d_section_workflow(
                hfss,
                recipe,
                result_dir,
                args,
                material_context,
            )
            detection["stages"].append(record)
            q2d, q2d_section_objects, record = ensure_q2d_target_design(
                hfss,
                recipe,
                manifest,
                section_objects,
                args,
                material_context,
            )
            detection["stages"].append(record)
            material_summary = assign_q2d_section_materials(
                q2d,
                mapping_payload,
                recipe,
                material_context,
            )
            detection["stages"].append(stage_record("materials", "repaired", **material_summary))
        region_recipe = (
            q2d_semantic_region_recipe(recipe, semantic_geometry_plan)
            if semantic_geometry_plan is not None
            else recipe
        )
        region_summary = create_q2d_region(q2d, region_recipe)
        detection["stages"].append(stage_record("region", "repaired", **region_summary))
        names = object_names(q2d)
        conductor_groups = []
        marker_assignment_done = False
        if semantic_geometry_plan is not None:
            assignment_summary = assign_q2d_semantic_conductors(
                q2d,
                semantic_geometry_plan,
                recipe,
            )
            detection["stages"].append(
                stage_record(
                    "conductor_assignment",
                    "repaired",
                    assignment_source="semantic_cross_section",
                    assignment_count=len(assignment_summary.get("assignments", [])),
                )
            )
            write_json(
                result_dir / "assignment_summary.json",
                {
                    "recipe_type": recipe["type"],
                    "assignment_source": "semantic_cross_section",
                    **assignment_summary,
                },
            )
        elif assignment_source == "q2d_conductors":
            conductor_groups = q2d_conductor_groups(load_q2d_conductor_rows(case, package_root))
            if not (recipe.get("signal_patterns") or recipe.get("ground_patterns")):
                assignment_summary = assign_q2d_conductor_groups_from_markers(
                    q2d,
                    conductor_groups,
                    recipe,
                    mapping_payload,
                    material_context,
                )
                detection["stages"].append(
                    stage_record(
                        "conductor_assignment",
                        "repaired",
                        assignment_source=assignment_source,
                        assignment_count=len(assignment_summary.get("assignments", [])),
                    )
                )
                write_json(
                    result_dir / "assignment_summary.json",
                    {
                        "recipe_type": recipe["type"],
                        "assignment_source": assignment_source,
                        "conductor_groups": conductor_groups,
                        **assignment_summary,
                    },
                )
                marker_assignment_done = True
            if not marker_assignment_done:
                assignment_summary = assign_q2d_object_pattern_conductors(
                    q2d,
                    names,
                    recipe,
                    conductor_groups,
                )
                detection["stages"].append(
                    stage_record(
                        "conductor_assignment",
                        "repaired",
                        assignment_source=assignment_source,
                    )
                )
                write_json(
                    result_dir / "assignment_summary.json",
                    assignment_summary,
                )
        setup = create_q2d_setup(q2d, recipe)
        detection["stages"].append(
            stage_record("setup", "repaired", setup=setup.name, setup_props=q2d_setup_props(recipe))
        )
        solve_status = {
            "mode": args.mode,
            "analyze_setup": None,
            "matrix_exports": [],
            "benchmark_exports": [],
            "physical_convergence": None,
            "stage_timing": [],
        }
        if args.mode == "solve":
            try:
                stage_timing = solve_status["stage_timing"]
                analyze_kwargs, hpc_payload = q2d_analyze_setup_kwargs(
                    args,
                    manifest,
                    package_root,
                    run_log_root(args, log_dir),
                )
                with aedt_blocking_stage_heartbeat(
                    log_dir,
                    "q2d_analyze_setup",
                    project_path=manifest["project"]["path"],
                    metadata={
                        "case_id": case["id"],
                        "recipe_id": recipe["id"],
                        "setup": setup.name,
                        "design": recipe["design_name"],
                        "hpc": hpc_payload,
                    },
                ):
                    analyze_ok = timed_stage(
                        stage_timing,
                        "analyze_setup",
                        q2d.analyze_setup,
                        setup.name,
                        **analyze_kwargs,
                    )
                solve_status["analyze_setup"] = {
                    "setup": setup.name,
                    "return_value": bool(analyze_ok),
                    "hpc": hpc_payload,
                }
                if not analyze_ok:
                    raise RuntimeError(f"Q2D analyze_setup failed for setup {setup.name}")
                with aedt_blocking_stage_heartbeat(
                    log_dir,
                    "q2d_export_matrices",
                    project_path=manifest["project"]["path"],
                    extra_paths={"result_dir": result_dir},
                    metadata={
                        "case_id": case["id"],
                        "recipe_id": recipe["id"],
                        "setup": setup.name,
                        "design": recipe["design_name"],
                    },
                ):
                    matrix_exports = timed_stage(
                        stage_timing,
                        "export_q2d_matrices",
                        export_q2d_matrices,
                        q2d,
                        recipe,
                        result_dir,
                    )
                solve_status["matrix_exports"] = matrix_exports
                exported_files.extend(record["file_name"] for record in matrix_exports)
                benchmark_exports = export_aedt_benchmark_artifacts(
                    q2d,
                    setup.name,
                    result_dir,
                    solver_type=recipe["type"],
                    problem_types=recipe.get("matrix_problem_types", ("CG", "RL")),
                    stage_timing=stage_timing,
                )
                solve_status["benchmark_exports"] = benchmark_exports
                exported_files.extend(
                    record["file_name"]
                    for record in benchmark_exports
                    if record.get("file_name") and record.get("return_value")
                )
                started_at = time.monotonic()
                physical_convergence = export_q2d_physical_convergence(q2d, recipe, result_dir)
                stage_timing.append(
                    elapsed_stage_record(
                        "export_q2d_physical_convergence",
                        started_at,
                        return_value=physical_convergence.get("status") == "created",
                    )
                )
                solve_status["physical_convergence"] = physical_convergence
                write_json(
                    result_dir / "q2d_physical_convergence_export_status.json",
                    physical_convergence,
                )
                write_json(result_dir / "solve_timing.json", {"stage_timing": stage_timing})
            except Exception as exc:
                aedt_messages = collect_aedt_messages_from_app(q2d)
                if aedt_messages:
                    solve_status["aedt_messages"] = aedt_messages
                    log(log_dir, "AEDT messages: " + json.dumps(aedt_messages))
                detection["stages"].append(
                    stage_record(
                        "solve_export",
                        "failed",
                        solve_status=solve_status,
                        error=str(exc),
                    )
                )
                raise
            detection["stages"].append(
                stage_record(
                    "solve_export",
                    "created",
                    solve_status=solve_status,
                    exported_files=list(exported_files),
                )
            )
        write_json(
            result_dir / "simulation_metadata.json",
            {
                "recipe_type": recipe["type"],
                "q2d_geometry_mode": geometry_mode,
                "hfss_staging_design": getattr(hfss, "design_name", None),
                "q2d_design": getattr(q2d, "design_name", None),
                "setup": setup.name,
                "imported_object_count": len(imported_objects),
                "section_object_count": len(section_objects),
                "q2d_section_object_count": len(q2d_section_objects),
                "modeler_units": recipe_modeler_units(recipe),
                "material_policy": recipe.get("material_policy", {}),
                "aedt_material_context": {
                    "schema_version": material_context.get("schema_version"),
                    "material_condition": material_context.get("material_condition"),
                    "registry_hash": material_context.get("registry_hash"),
                    "layer_stack_hash": material_context.get("layer_stack_hash"),
                    "binding_count": len(material_context_bindings(material_context)),
                    "material_count": len(material_context_compiled_materials(material_context)),
                },
                "q2d_region": region_summary,
                "q2d_setup": setup_summary(recipe, setup),
                "solve_status": solve_status,
                "exported_files": list(exported_files),
                "incremental_state": {
                    "adopted_existing": adopted_existing,
                    "stage_count": len(detection["stages"]),
                },
            },
        )
        completion = q2d_solve_completion_status(result_dir, log_dir, recipe)
        workflow_state.update(
            {
                "status_schema_version": "aedt-q2d-workflow-state.v2",
                **completion,
                "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                if completion.get("completion_status") == "complete"
                else None,
            }
        )
        workflow_state["stage_decisions"] = list(detection["stages"])
        write_q2d_stage_outputs(log_dir, detection, workflow_state)
        q2d.save_project()
    except Exception:
        detection["error"] = traceback.format_exc()
        workflow_state["stage_decisions"] = list(detection["stages"])
        workflow_state["error"] = detection["error"]
        workflow_state["status_schema_version"] = "aedt-q2d-workflow-state.v2"
        workflow_state["completion_status"] = "failed"
        workflow_state["failure_kind"] = "exception"
        write_q2d_stage_outputs(log_dir, detection, workflow_state)
        raise


def validate_previous_q2d_state(
    previous_state,
    source_hashes,
    geometry_settings_hash,
    recipe_settings_hash,
    args,
    detection,
):
    if not previous_state or args.force_rebuild:
        return
    if previous_state.get("source_hashes") != source_hashes:
        record = stage_record(
            "state_validation",
            "stale",
            reason="source artifact hashes changed",
            previous=previous_state.get("source_hashes"),
            current=source_hashes,
        )
        detection["stages"].append(record)
        raise RuntimeError("Q2D source artifacts changed; rerun with --force-rebuild")
    if previous_state.get("geometry_settings_hash") != geometry_settings_hash:
        record = stage_record(
            "state_validation",
            "stale",
            reason="geometry-affecting recipe settings changed",
        )
        detection["stages"].append(record)
        raise RuntimeError("Q2D geometry settings changed; rerun with --force-rebuild")
    if previous_state.get("recipe_settings_hash") != recipe_settings_hash:
        record = stage_record(
            "state_validation",
            "stale",
            reason="recipe settings changed",
            previous=previous_state.get("recipe_settings_hash"),
            current=recipe_settings_hash,
        )
        detection["stages"].append(record)
        raise RuntimeError("Q2D recipe settings changed; rerun with --force-rebuild")
    detection["stages"].append(stage_record("state_validation", "valid"))


def ensure_q2d_staging_hfss(
    case,
    recipe,
    manifest,
    package_root,
    result_dir,
    log_dir,
    args,
    material_context,
):
    from ansys.aedt.core import Hfss

    mapping_payload = load_layer_mapping(case, package_root)
    mapping_layers = q2d_import_mapping_layers(mapping_payload, recipe_modeler_units(recipe))
    staging_design = f"{recipe['design_name']}_hfss_staging"
    hfss = create_aedt_app(
        Hfss,
        args,
        project=manifest["project"]["path"],
        design=staging_design,
        **aedt_constructor_kwargs(args),
    )
    ensure_design_modeler_units(hfss, recipe, "q2d_hfss_staging")
    material_summary = ensure_aedt_project_materials(hfss, material_context, result_dir)
    if args.force_rebuild:
        clear_recipe_design(hfss)
    existing_imported = imported_modeler_object_names(hfss)
    if existing_imported and not args.force_rebuild:
        renames = rename_modeler_objects_for_layer_stack(hfss, material_context, section_only=False)
        assign_imported_materials(
            hfss,
            mapping_payload.get("gds_import_layers", []),
            recipe,
            material_context,
        )
        existing_imported = imported_modeler_object_names(hfss)
        imported_objects = [
            record
            for record in object_inventory(hfss, material_context)
            if record["name"] in existing_imported
        ]
        write_json(result_dir / "object_inventory_imported.json", imported_objects)
        return (
            hfss,
            imported_objects,
            mapping_payload,
            stage_record(
                "hfss_import",
                "skipped",
                object_count=len(imported_objects),
                adopted_existing=True,
                material_summary=material_summary,
                renames=renames,
            ),
        )
    gds_path = package_path(package_root, case["gds"])
    with aedt_blocking_stage_heartbeat(
        log_dir,
        "q2d_hfss_import_gds_3d",
        project_path=manifest["project"]["path"],
        extra_paths={"gds": gds_path, "result_dir": result_dir},
        metadata={"case_id": case["id"], "recipe_id": recipe["id"], "design": staging_design},
    ):
        ok = hfss.import_gds_3d(
            str(gds_path),
            mapping_layers,
            units=recipe_modeler_units(recipe),
            import_method=1,
        )
    if not ok:
        raise RuntimeError(f"Hfss.import_gds_3d failed for case {case['id']}")
    renames = rename_modeler_objects_for_layer_stack(hfss, material_context, section_only=False)
    assign_imported_materials(
        hfss,
        mapping_payload.get("gds_import_layers", []),
        recipe,
        material_context,
    )
    imported_names = imported_modeler_object_names(hfss)
    imported_objects = [
        record
        for record in object_inventory(hfss, material_context)
        if record["name"] in imported_names
    ]
    write_json(result_dir / "object_inventory_imported.json", imported_objects)
    return (
        hfss,
        imported_objects,
        mapping_payload,
        stage_record(
            "hfss_import",
            "created",
            object_count=len(imported_objects),
            material_summary=material_summary,
            renames=renames,
        ),
    )


def ensure_q2d_section_workflow(hfss, recipe, result_dir, args, material_context):
    existing_sections = section_modeler_object_names(hfss)
    if existing_sections and not args.force_rebuild:
        renames = rename_modeler_objects_for_layer_stack(hfss, material_context, section_only=True)
        existing_sections = section_modeler_object_names(hfss)
        excluded_existing_sections = q2d_excluded_section_records(hfss, material_context)
        if excluded_existing_sections:
            raise RuntimeError(
                "Existing HFSS Q2D section state contains objects that are excluded "
                "from the current Q2D section contract. Rerun with --force-rebuild. "
                f"Excluded sections: {excluded_existing_sections}"
            )
        write_q2d_section_artifacts(hfss, recipe, result_dir, existing_sections)
        return (
            existing_sections,
            stage_record(
                "hfss_section",
                "skipped",
                section_object_count=len(existing_sections),
                renames=renames,
            ),
        )
    section_objects = apply_q2d_section_workflow(hfss, recipe, result_dir, material_context)
    return (
        section_objects,
        stage_record("hfss_section", "created", section_object_count=len(section_objects)),
    )


def ensure_q2d_target_design(hfss, recipe, manifest, section_objects, args, material_context):
    from ansys.aedt.core import Q2d

    q2d = create_aedt_app(
        Q2d,
        args,
        project=manifest["project"]["path"],
        design=recipe["design_name"],
        **aedt_constructor_kwargs(args, new_desktop=False),
    )
    ensure_design_modeler_units(q2d, recipe, "q2d_target")
    ensure_aedt_project_materials(q2d, material_context)
    if args.force_rebuild:
        clear_recipe_design(q2d, clear_setups=True)
    existing_sections = section_modeler_object_names(q2d)
    if existing_sections and not args.force_rebuild:
        renames = rename_modeler_objects_for_layer_stack(q2d, material_context, section_only=True)
        existing_sections = section_modeler_object_names(q2d)
        excluded_existing_sections = q2d_excluded_section_records(q2d, material_context)
        if excluded_existing_sections:
            raise RuntimeError(
                "Existing Q2D target design contains objects that are excluded from "
                "the current Q2D section contract. Rerun with --force-rebuild. "
                f"Excluded sections: {excluded_existing_sections}"
            )
        return (
            q2d,
            existing_sections,
            stage_record(
                "q2d_copy",
                "skipped",
                section_object_count=len(existing_sections),
                adopted_existing=True,
                renames=renames,
            ),
        )
    ok = q2d.copy_solid_bodies_from(
        hfss,
        assignment=section_objects,
        include_sheets=True,
        no_vacuum=False,
        no_pec=False,
    )
    if not ok:
        raise RuntimeError("Failed to copy HFSS section objects into Q2D design")
    renames = rename_modeler_objects_for_layer_stack(q2d, material_context, section_only=True)
    copied_sections = section_modeler_object_names(q2d)
    return (
        q2d,
        copied_sections,
        stage_record(
            "q2d_copy",
            "created",
            section_object_count=len(copied_sections),
            renames=renames,
        ),
    )


def ensure_q2d_semantic_cross_section_geometry(
    case,
    recipe,
    manifest,
    package_root,
    result_dir,
    args,
    material_context,
):
    from ansys.aedt.core import Q2d

    q2d = create_aedt_app(
        Q2d,
        args,
        project=manifest["project"]["path"],
        design=recipe["design_name"],
        **aedt_constructor_kwargs(args, new_desktop=False),
    )
    ensure_design_modeler_units(q2d, recipe, "q2d_target")
    material_summary = ensure_aedt_project_materials(q2d, material_context, result_dir)
    payload = load_q2d_semantic_cross_section(case, package_root)
    plan = q2d_semantic_geometry_plan(payload)
    write_json(result_dir / "q2d_semantic_geometry_plan.json", plan)

    planned_names = {rectangle["name"] for rectangle in plan["rectangles"]}
    existing_names = set(modeler_object_names(q2d))
    region_name = str((plan.get("region") or {}).get("name") or "Vacuum")
    if args.force_rebuild:
        clear_recipe_design(q2d, clear_setups=True)
        existing_names = set()
    elif planned_names.issubset(existing_names):
        extra_names = existing_names - planned_names - {region_name}
        if extra_names:
            raise RuntimeError(
                "Existing Q2D design has extra objects. Rerun with --force-rebuild. "
                f"Extra objects: {sorted(extra_names)}"
            )
        inventory = object_inventory(q2d, material_context)
        write_json(result_dir / "q2d_semantic_object_inventory.json", inventory)
        return (
            q2d,
            sorted(planned_names),
            plan,
            stage_record(
                "semantic_geometry",
                "skipped",
                object_count=len(planned_names),
                adopted_existing=True,
                material_summary=material_summary,
            ),
        )
    elif existing_names - {region_name}:
        raise RuntimeError(
            "Existing Q2D design has non-semantic objects. Rerun with --force-rebuild. "
            f"Existing objects: {sorted(existing_names)}"
        )

    created_names = create_q2d_semantic_rectangles(q2d, plan, recipe)
    inventory = object_inventory(q2d, material_context)
    write_json(result_dir / "q2d_semantic_object_inventory.json", inventory)
    return (
        q2d,
        created_names,
        plan,
        stage_record(
            "semantic_geometry",
            "created",
            object_count=len(created_names),
            material_summary=material_summary,
        ),
    )


def create_q2d_semantic_rectangles(q2d, plan, recipe):
    units = recipe_modeler_units(recipe)
    created_names = []
    for rectangle in plan["rectangles"]:
        origin = [um_to_modeler_units(float(value), units) for value in rectangle["origin_um"]]
        sizes = [um_to_modeler_units(float(value), units) for value in rectangle["sizes_um"]]
        create_rectangle = getattr(q2d, "create_rectangle", None)
        if callable(create_rectangle):
            obj = create_rectangle(
                origin=origin,
                sizes=sizes,
                name=rectangle["name"],
                material=rectangle["material"],
            )
        else:
            obj = q2d.modeler.create_rectangle(
                origin=[origin[0], origin[1], 0],
                sizes=sizes,
                name=rectangle["name"],
                material=rectangle["material"],
            )
        if obj is None:
            raise RuntimeError(f"Failed to create Q2D semantic rectangle {rectangle['name']!r}")
        created_names.append(getattr(obj, "name", rectangle["name"]))
    return created_names


def q2d_semantic_region_recipe(recipe, plan):
    updated = dict(recipe)
    region = dict(updated.get("q2d_region") or {})
    payload_region = plan.get("region") or {}
    if payload_region.get("name"):
        region["name"] = payload_region["name"]
    if payload_region.get("material"):
        region["material"] = payload_region["material"]
    padding = dict(region.get("padding") or {})
    for direction, value in plan.get("region_padding_um", {}).items():
        if value is not None:
            padding[direction] = f"{float(value):g}um"
    region["padding"] = {
        direction: str(padding.get(direction, "0um")) for direction in ("+X", "-X", "+Y", "-Y")
    }
    updated["q2d_region"] = region
    return updated


def assign_q2d_semantic_conductors(q2d, plan, recipe):
    assignment_names = set(plan["assignments"])
    delete_boundaries_by_name(q2d, assignment_names)
    units = recipe_modeler_units(recipe)
    assignments = []
    for assignment in plan["assignments"].values():
        objects = [q2d.modeler.get_object_from_name(name) for name in assignment["objects"]]
        if any(obj is None for obj in objects):
            raise RuntimeError(
                f"Q2D semantic assignment objects were not found: {assignment['objects']}"
            )
        boundary = q2d.assign_single_conductor(
            objects,
            name=assignment["assignment_name"],
            conductor_type=q2d_conductor_type_for_aedt(assignment["conductor_type"]),
            units=units,
        )
        assignments.append(
            {
                **assignment,
                "boundary": getattr(boundary, "name", assignment["assignment_name"]),
            }
        )
    return {"assignments": assignments}


def write_q2d_section_artifacts(
    hfss,
    recipe,
    result_dir,
    section_objects,
    *,
    section_candidates=None,
    excluded_section_candidates=None,
):
    write_json(
        result_dir / "q2d_section_plan.json",
        {
            "section_plane": recipe.get("section_plane", "XY"),
            "rotations": recipe.get("rotations", []),
            "source_design": getattr(hfss, "design_name", None),
            "section_candidates": list(section_candidates or []),
            "excluded_section_candidates": list(excluded_section_candidates or []),
            "section_object_count": len(section_objects),
        },
    )
    write_json(
        result_dir / "q2d_section_inventory.json",
        [
            {
                "name": name,
                "bounding_box": object_bounding_box(hfss.modeler.get_object_from_name(name)),
            }
            for name in section_objects
        ],
    )


def assign_q2d_object_pattern_conductors(q2d, names, recipe, conductor_groups):
    signal_matches = match_patterns(
        names,
        recipe["signal_patterns"],
        label="Q2D signal patterns",
        exact_count=1,
    )
    ground_matches = match_patterns(
        names,
        recipe["ground_patterns"],
        label="Q2D ground patterns",
        min_count=2,
    )
    delete_boundaries_by_name(q2d, {"SignalLine", "ReferenceGround"})
    signal_boundary = q2d.assign_single_conductor(
        signal_matches,
        name="SignalLine",
        conductor_type="SignalLine",
        units="um",
    )
    ground_boundary = q2d.assign_single_conductor(
        ground_matches,
        name="ReferenceGround",
        conductor_type="ReferenceGround",
        units="um",
    )
    return {
        "recipe_type": recipe["type"],
        "assignment_source": recipe.get("assignment_source") or "object_patterns",
        "conductor_groups": conductor_groups,
        "signal_matches": signal_matches,
        "ground_matches": ground_matches,
        "signal_boundary": getattr(signal_boundary, "name", "SignalLine"),
        "ground_boundary": getattr(ground_boundary, "name", "ReferenceGround"),
    }


def import_q2d_staging_hfss(case, recipe, manifest, package_root, result_dir, args):
    from ansys.aedt.core import Hfss

    mapping_payload = load_layer_mapping(case, package_root)
    material_context = load_aedt_material_context(case, package_root)
    mapping_layers = q2d_import_mapping_layers(mapping_payload, recipe_modeler_units(recipe))
    staging_design = f"{recipe['design_name']}_hfss_staging"
    hfss = create_aedt_app(
        Hfss,
        args,
        project=manifest["project"]["path"],
        design=staging_design,
        **aedt_constructor_kwargs(args),
    )
    ensure_design_modeler_units(hfss, recipe, "q2d_hfss_staging")
    ensure_aedt_project_materials(hfss, material_context, result_dir)
    gds_path = package_path(package_root, case["gds"])
    with aedt_blocking_stage_heartbeat(
        result_dir,
        "q2d_hfss_import_gds_3d",
        project_path=manifest["project"]["path"],
        extra_paths={"gds": gds_path, "result_dir": result_dir},
        metadata={"case_id": case["id"], "recipe_id": recipe["id"], "design": staging_design},
    ):
        ok = hfss.import_gds_3d(
            str(gds_path),
            mapping_layers,
            units=recipe_modeler_units(recipe),
            import_method=1,
        )
    if not ok:
        raise RuntimeError(f"Hfss.import_gds_3d failed for case {case['id']}")
    rename_modeler_objects_for_layer_stack(hfss, material_context, section_only=False)
    assign_imported_materials(
        hfss,
        mapping_payload.get("gds_import_layers", []),
        recipe,
        material_context,
    )
    imported_objects = object_inventory(hfss, material_context)
    write_json(result_dir / "object_inventory_imported.json", imported_objects)
    return hfss, imported_objects, mapping_payload


def load_layer_mapping(case, package_root):
    relative = case.get("layer_mapping_json")
    if not relative:
        raise RuntimeError(f"Case {case['id']} has no layer_mapping_json sidecar")
    return json.loads(package_path(package_root, relative).read_text(encoding="utf-8"))


def q2d_import_mapping_layers(mapping_payload, modeler_units="um"):
    rows = mapping_payload.get("gds_import_layers") or mapping_payload.get("layers") or []
    mapping_layers = {}
    layer_sources = {}
    for row in rows:
        if row.get("aedt_import_policy") not in (None, "gds_import"):
            continue
        layer = int(row["aedt_layer_number"])
        zmin = um_to_modeler_units(float(row["aedt_import_zmin_um"]), modeler_units)
        thickness = um_to_modeler_units(float(row["aedt_import_thickness_um"]), modeler_units)
        previous = mapping_layers.get(layer)
        source = row.get("layer_name") or row.get("aedt_layer_tuple") or layer
        if previous is not None:
            raise RuntimeError(
                "Q2D GDS import requires one mapping row per AEDT virtual layer number; "
                f"layer {layer} is used by both {layer_sources[layer]!r} and {source!r}."
            )
        mapping_layers[layer] = (zmin, thickness)
        layer_sources[layer] = source
    if not mapping_layers:
        raise RuntimeError("Q2D import requires at least one GDS import layer")
    return mapping_layers


def desired_layer_object_renames(object_names, material_context, *, section_only=None):
    grouped = {}
    for name in sorted(str(item) for item in object_names):
        is_section = "_section" in name.casefold()
        if section_only is True and not is_section:
            continue
        if section_only is False and is_section:
            continue
        binding = material_context_binding_for_object_name(name, material_context)
        if binding is None or binding.get("role") == "vacuum_volume":
            continue
        base = str(binding.get("object_name_base") or "").strip()
        if not base:
            continue
        grouped.setdefault(base, []).append((name, binding, is_section))

    renames = []
    for base, items in sorted(grouped.items()):
        count = len(items)
        for index, (old_name, binding, is_section) in enumerate(sorted(items), start=1):
            desired = desired_layer_object_name(base, index, count, section=is_section)
            renames.append(
                {
                    "old_name": old_name,
                    "new_name": desired,
                    "layer_name": binding.get("layer_name"),
                    "object_name_base": base,
                    "aedt_layer_number": binding.get("aedt_layer_number"),
                    "physical_material_key": binding.get("physical_material_key"),
                    "aedt_material_name": binding.get("aedt_material_name"),
                    "aedt_material_fallback_reason": binding.get("aedt_material_fallback_reason"),
                    "role": binding.get("role"),
                    "changed": old_name != desired,
                }
            )
    return renames


def desired_layer_object_name(base, index, count, *, section):
    stem = base if count == 1 else f"{base}_{index}"
    return f"{stem}_Section1" if section else stem


def rename_modeler_objects_for_layer_stack(app, material_context, *, section_only=None):
    renames = desired_layer_object_renames(
        modeler_object_names(app),
        material_context,
        section_only=section_only,
    )
    existing = set(modeler_object_names(app))
    pending_old_names = {record["old_name"] for record in renames if record["changed"]}
    for record in renames:
        if not record["changed"]:
            continue
        new_name = record["new_name"]
        if new_name in existing and new_name not in pending_old_names:
            raise RuntimeError(
                f"Cannot rename AEDT object {record['old_name']!r} to {new_name!r}; "
                "target name already exists"
            )
        rename_modeler_object(app, record["old_name"], new_name)
        existing.discard(record["old_name"])
        existing.add(new_name)
    return renames


def rename_modeler_object(app, old_name, new_name):
    if old_name == new_name:
        return new_name
    modeler = getattr(app, "modeler", None)
    if modeler is None:
        raise RuntimeError("AEDT app has no modeler for object rename")
    rename = getattr(modeler, "rename_object", None)
    if callable(rename):
        try:
            ok = rename(old_name, new_name)
            if ok is not False:
                return new_name
        except Exception:
            pass
    obj = modeler.get_object_from_name(old_name)
    if obj is None:
        raise RuntimeError(f"AEDT object {old_name!r} was not found for rename")
    try:
        obj.name = new_name
    except Exception as exc:
        raise RuntimeError(f"Failed to rename AEDT object {old_name!r} to {new_name!r}") from exc
    return new_name


def assign_imported_materials(app, rows, recipe, material_context=None):
    material_by_layer = {
        int(row["aedt_layer_number"]): material_for_import_row(row, recipe, material_context)
        for row in rows
        if row.get("aedt_layer_number") not in (None, "")
    }
    for name in modeler_object_names(app):
        if "_section" in str(name).casefold():
            continue
        provenance = object_layer_provenance(name, material_context)
        layer = (
            provenance.get("aedt_layer_number")
            if provenance
            else layer_number_from_object_name(name)
        )
        material = (
            provenance.get("aedt_material_name") if provenance else material_by_layer.get(layer)
        )
        if not material:
            continue
        obj = app.modeler.get_object_from_name(name)
        if obj is None:
            raise RuntimeError(f"Failed to resolve AEDT object for material assignment: {name!r}")
        try:
            obj.material_name = material
        except Exception as exc:
            raise RuntimeError(
                f"Failed to assign AEDT material {material!r} to object {name!r}"
            ) from exc


def material_for_import_row(row, recipe, material_context=None):
    context_material = (
        material_context_material_for_row(row, material_context) if material_context else None
    )
    if context_material:
        return context_material
    if is_conductor_import_row(row):
        return normalize_aedt_material(
            (recipe.get("material_policy") or {}).get("conductor_material") or "pec"
        )
    return normalize_aedt_material(row.get("material"))


def is_conductor_import_row(row):
    role = str(row.get("recommended_aedt_role") or "")
    destination = str(row.get("aedt_destination") or "")
    return role == "conductor" or destination.startswith("SCmetal")


def normalize_aedt_material(material):
    text = str(material or "").strip()
    if not text:
        return ""
    aliases = {
        "si": "Silicon",
        "silicon": "Silicon",
        "vacuum": "Vacuum",
        "al": "aluminum",
        "nb": "niobium",
        "in": "indium",
        "pec": "pec",
    }
    return aliases.get(text.casefold(), text)


def object_inventory(app, material_context=None):
    records = []
    for name in modeler_object_names(app):
        obj = app.modeler.get_object_from_name(name)
        record = {
            "name": name,
            "material": safe_material_name(obj),
            "bounding_box": object_bounding_box(obj),
        }
        record.update(object_layer_provenance(name, material_context))
        records.append(record)
    return records


def object_layer_provenance(name, material_context):
    if not material_context:
        return {}
    binding = material_context_binding_for_object_name(name, material_context)
    if binding is None:
        return {}
    return {
        "layer_name": binding.get("layer_name"),
        "object_name_base": binding.get("object_name_base"),
        "aedt_layer_number": binding.get("aedt_layer_number"),
        "physical_material_key": binding.get("physical_material_key"),
        "aedt_material_name": binding.get("aedt_material_name"),
        "aedt_material_fallback_reason": binding.get("aedt_material_fallback_reason"),
        "role": binding.get("role"),
    }


def safe_material_name(obj):
    if obj is None:
        return None
    try:
        return getattr(obj, "material_name", None)
    except Exception:
        return None


def modeler_object_names(app):
    modeler = getattr(app, "modeler", None)
    if modeler is None:
        return []
    names = []
    for attr in ("solid_names", "sheet_names", "object_names"):
        value = getattr(modeler, attr, None)
        if value is None:
            continue
        try:
            names.extend(str(item) for item in value)
        except TypeError:
            pass
    return sorted(set(names))


def object_bounding_box(obj):
    if obj is None:
        return None
    for attr in ("bounding_box", "bounding_dimension"):
        value = getattr(obj, attr, None)
        if value is None:
            continue
        try:
            return [float(item) for item in value]
        except TypeError:
            pass
    return None


def imported_modeler_object_names(app):
    return [
        name
        for name in modeler_object_names(app)
        if "_section" not in str(name).casefold()
        and str(name).casefold() not in {"region", "vacuum"}
    ]


def section_modeler_object_names(app):
    return sorted(name for name in modeler_object_names(app) if "_section" in str(name).casefold())


def q2d_section_source_partition(app, material_context=None):
    imported_names = set(imported_modeler_object_names(app))
    candidate_records = []
    excluded_records = []
    for record in object_inventory(app, material_context):
        name = str(record.get("name") or "")
        if name not in imported_names:
            continue
        reason = q2d_section_exclusion_reason(record)
        if reason:
            excluded = dict(record)
            excluded["q2d_section_exclusion_reason"] = reason
            excluded_records.append(excluded)
        else:
            candidate_records.append(record)
    return {
        "candidates": [str(record["name"]) for record in candidate_records],
        "excluded": [str(record["name"]) for record in excluded_records],
        "candidate_records": candidate_records,
        "excluded_records": excluded_records,
    }


def q2d_section_exclusion_reason(record):
    layer_name = str(record.get("layer_name") or "").upper()
    role = str(record.get("role") or "").casefold()
    if "INDIUM" in layer_name or "UNDER_BUMP" in layer_name:
        return "Q2D CPW section excludes discrete flip-chip bump geometry"
    if role == "vacuum_volume":
        return "Q2D creates vacuum as an explicit Region, not a sectioned GDS object"
    if role in {"junction_or_solver_sheet", "sheet"}:
        return "Q2D CPW section excludes solver sheet geometry"
    if role == "conductor" and layer_name and not layer_name.endswith("_M1"):
        return "Q2D CPW section includes M1 conductors only"
    return None


def q2d_excluded_section_records(app, material_context=None):
    section_names = set(section_modeler_object_names(app))
    excluded_records = []
    for record in object_inventory(app, material_context):
        name = str(record.get("name") or "")
        if name not in section_names:
            continue
        reason = q2d_section_exclusion_reason(record)
        if reason:
            excluded = dict(record)
            excluded["q2d_section_exclusion_reason"] = reason
            excluded_records.append(excluded)
    return excluded_records


def delete_modeler_objects(app, names=None):
    names = list(names if names is not None else modeler_object_names(app))
    if not names:
        return True
    try:
        return bool(app.modeler.delete(names))
    except Exception:
        ok = True
        for name in names:
            try:
                obj = app.modeler.get_object_from_name(name)
                if obj is not None:
                    obj.delete()
            except Exception:
                ok = False
        return ok


def delete_existing_setup(app, setup_name):
    for setup in list(getattr(app, "setups", [])):
        if getattr(setup, "name", None) == setup_name:
            try:
                return bool(setup.delete())
            except Exception:
                pass
    try:
        if setup_name in getattr(app, "setup_names", []):
            app.oanalysis.DeleteSetups([setup_name])
            return True
    except Exception:
        pass
    return False


def get_setup_by_name(app, setup_name):
    for setup in getattr(app, "setups", []):
        if getattr(setup, "name", None) == setup_name:
            return setup
    return None


def delete_boundaries_by_name(app, names):
    names = set(names)
    for boundary in list(getattr(app, "boundaries", [])):
        if getattr(boundary, "name", None) not in names:
            continue
        try:
            boundary.delete()
        except Exception:
            pass


def clear_recipe_design(app, *, clear_setups=False):
    delete_modeler_objects(app)
    if clear_setups:
        for setup_name in list(getattr(app, "setup_names", [])):
            delete_existing_setup(app, setup_name)
    for boundary in list(getattr(app, "boundaries", [])):
        try:
            boundary.delete()
        except Exception:
            pass


def apply_q2d_section_workflow(hfss, recipe, result_dir, material_context=None):
    source_partition = q2d_section_source_partition(hfss, material_context)
    object_names_before_rotation = list(source_partition["candidates"])
    if not object_names_before_rotation:
        raise RuntimeError(
            "HFSS staging has no Q2D section-eligible objects. "
            f"Excluded objects: {source_partition['excluded']}"
        )
    for rotation in recipe.get("rotations", []):
        hfss.modeler.rotate(
            object_names_before_rotation,
            rotation["axis"],
            angle=float(rotation["angle_deg"]),
            units="deg",
        )
    before_section = set(modeler_object_names(hfss))
    section_plane = recipe.get("section_plane", "XY")
    ok = hfss.modeler.section(
        object_names_before_rotation,
        section_plane,
        create_new=True,
        section_cross_object=False,
    )
    if not ok:
        raise RuntimeError(f"HFSS staging section failed on plane {section_plane}")
    after_section = set(modeler_object_names(hfss))
    section_objects = sorted(after_section - before_section)
    if not section_objects:
        raise RuntimeError("HFSS staging section produced no new section objects")
    rename_modeler_objects_for_layer_stack(hfss, material_context, section_only=True)
    section_objects = section_modeler_object_names(hfss)
    write_q2d_section_artifacts(
        hfss,
        recipe,
        result_dir,
        section_objects,
        section_candidates=source_partition["candidate_records"],
        excluded_section_candidates=source_partition["excluded_records"],
    )
    return section_objects


def create_q2d_target_design(hfss, recipe, manifest, section_objects, args):
    from ansys.aedt.core import Q2d

    q2d = create_aedt_app(
        Q2d,
        args,
        project=manifest["project"]["path"],
        design=recipe["design_name"],
        **aedt_constructor_kwargs(args, new_desktop=False),
    )
    ensure_design_modeler_units(q2d, recipe, "q2d_target")
    ok = q2d.copy_solid_bodies_from(
        hfss,
        assignment=section_objects,
        include_sheets=True,
        no_vacuum=False,
        no_pec=False,
    )
    if not ok:
        raise RuntimeError("Failed to copy HFSS section objects into Q2D design")
    return q2d


def assign_q2d_section_materials(q2d, mapping_payload, recipe, material_context=None):
    ensure_aedt_project_materials(q2d, material_context)
    conductor_layers = conductor_layer_numbers_from_mapping(mapping_payload)
    conductor_material = normalize_aedt_material(
        (recipe.get("material_policy") or {}).get("conductor_material") or "pec"
    )
    rows_by_layer = {
        int(row["aedt_layer_number"]): row
        for row in mapping_payload.get("gds_import_layers", [])
        if row.get("aedt_layer_number") not in (None, "")
    }
    assigned = []
    for name in modeler_object_names(q2d):
        provenance = object_layer_provenance(name, material_context)
        layer = (
            provenance.get("aedt_layer_number")
            if provenance
            else layer_number_from_object_name(name)
        )
        if provenance.get("aedt_material_name"):
            material = provenance["aedt_material_name"]
        elif layer in conductor_layers:
            material = conductor_material
        else:
            material = normalize_aedt_material(rows_by_layer.get(layer, {}).get("material"))
        if not material:
            continue
        obj = q2d.modeler.get_object_from_name(name)
        if obj is None:
            raise RuntimeError(f"Failed to resolve Q2D object for material assignment: {name!r}")
        try:
            obj.material_name = material
            assigned.append({"name": name, "material": material, **provenance})
        except Exception as exc:
            raise RuntimeError(
                f"Failed to assign Q2D material {material!r} to object {name!r}"
            ) from exc
    return {"assigned_count": len(assigned), "assigned": assigned}


def create_q2d_region(q2d, recipe):
    region = recipe.get("q2d_region") or {}
    if not region.get("enabled", True):
        return {"enabled": False}
    padding = region.get("padding") or {}
    directions = ["+X", "-X", "+Y", "-Y"]
    values = [str(padding.get(direction, "0um")) for direction in directions]
    padding_type = str(region.get("padding_type") or "Absolute Offset")
    name = str(region.get("name") or "Vacuum")
    material = normalize_aedt_material(region.get("material") or "Vacuum")
    mode = str(region.get("mode") or "individual")
    existing = q2d.modeler.get_object_from_name(name)
    if existing is not None:
        try:
            existing.delete()
        except Exception:
            delete_modeler_objects(q2d, [name])
    values_by_direction = dict(zip(directions, values, strict=True))
    if mode == "all":
        pad_value = values[0]
    else:
        # PyAEDT 2D create_region reorders list input as [0, 2, 1, 3].
        # Pass the inverse order so AEDT receives +X, -X, +Y, -Y as requested.
        pyaedt_directions = ["+X", "+Y", "-X", "-Y"]
        pad_value = [values_by_direction[direction] for direction in pyaedt_directions]
    obj = q2d.modeler.create_region(
        pad_value=pad_value,
        pad_type=padding_type,
        name=name,
    )
    if material:
        obj.material_name = material
    return {
        "enabled": True,
        "name": getattr(obj, "name", name),
        "material": material,
        "mode": mode,
        "padding_type": padding_type,
        "padding": values_by_direction,
    }


def assign_q2d_conductor_groups_from_markers(
    q2d,
    conductor_groups,
    recipe,
    mapping_payload,
    material_context=None,
):
    object_records = object_inventory(q2d, material_context)
    conductor_layers = conductor_layer_numbers_from_mapping(mapping_payload)
    conductor_records = [
        record
        for record in object_records
        if record.get("role") == "conductor"
        or layer_number_from_object_name(record["name"]) in conductor_layers
    ]
    resolved_assignments = resolve_q2d_marker_assignments(
        conductor_groups,
        conductor_records,
        recipe,
    )
    assignments = []
    delete_boundaries_by_name(q2d, {group["assignment_name"] for group in conductor_groups})
    units = recipe_modeler_units(recipe)
    for assignment in resolved_assignments:
        unique_objects = assignment["objects"]
        assignment_objects = [q2d.modeler.get_object_from_name(name) for name in unique_objects]
        if any(obj is None for obj in assignment_objects):
            raise RuntimeError(f"Q2D assignment objects were not found: {unique_objects}")
        boundary = q2d.assign_single_conductor(
            assignment_objects,
            name=assignment["assignment_name"],
            conductor_type=q2d_conductor_type_for_aedt(assignment["conductor_type"]),
            units=units,
        )
        assignments.append(
            {
                **assignment,
                "boundary": getattr(boundary, "name", assignment["assignment_name"]),
            }
        )
    return {"assignments": assignments}


def resolve_q2d_marker_assignments(conductor_groups, conductor_records, recipe):
    assignments = []
    modeler_units = recipe_modeler_units(recipe)
    section_plane = recipe.get("section_plane", "XY")
    for group in conductor_groups:
        matched_objects = []
        marker_matches = []
        for marker in group["markers"]:
            source_point_um = marker_source_point_um(marker)
            marker_point = transformed_marker_point(
                marker,
                recipe.get("rotations", []),
                modeler_units,
            )
            matched_records = [
                record
                for record in conductor_records
                if point_in_section_bbox(
                    marker_point,
                    record.get("bounding_box"),
                    section_plane,
                )
            ]
            if len(matched_records) != 1:
                raise RuntimeError(
                    f"Q2D marker {marker['name']!r} expected exactly one section object, "
                    f"got {[record['name'] for record in matched_records]}; "
                    f"source_point_um={source_point_um}; "
                    f"transformed_point={marker_point}; "
                    f"modeler_units={modeler_units!r}; "
                    f"section_plane={section_plane!r}; "
                    f"candidate_bboxes={q2d_candidate_bbox_summary(conductor_records)}"
                )
            matched_record = matched_records[0]
            marker_matches.append(
                {
                    "marker": marker["name"],
                    "source_point_um": source_point_um,
                    "transformed_point": marker_point,
                    "modeler_units": modeler_units,
                    "marker_layer": marker.get("layer"),
                    "marker_layer_stack_layer_name": marker.get("layer_stack_layer_name"),
                    "object": matched_record["name"],
                    "object_bounding_box": matched_record.get("bounding_box"),
                    "layer_name": matched_record.get("layer_name"),
                    "object_name_base": matched_record.get("object_name_base"),
                    "physical_material_key": matched_record.get("physical_material_key"),
                    "aedt_material_name": matched_record.get("aedt_material_name"),
                    "aedt_material_fallback_reason": matched_record.get(
                        "aedt_material_fallback_reason"
                    ),
                }
            )
            matched_objects.append(matched_record["name"])
        assignments.append(
            {
                "assignment_name": group["assignment_name"],
                "conductor_type": group["conductor_type"],
                "objects": sorted(set(matched_objects)),
                "marker_matches": marker_matches,
            }
        )
    conflict = q2d_assignment_object_conflict(assignments)
    if conflict:
        raise RuntimeError(f"Q2D conductor assignment object conflict: {conflict}")
    return assignments


def marker_source_point_um(marker):
    return [
        float(marker.get("source_x_um", marker.get("center_x_um", 0.0))),
        float(marker.get("source_y_um", marker.get("center_y_um", 0.0))),
        float(marker.get("source_z_um", marker.get("center_z_um", 0.0))),
    ]


def q2d_candidate_bbox_summary(records):
    return [
        {"name": record.get("name"), "bounding_box": record.get("bounding_box")}
        for record in records
    ]


def q2d_assignment_object_conflict(assignments):
    owners_by_object = {}
    for assignment in assignments:
        owner = assignment["assignment_name"]
        for name in assignment["objects"]:
            owners_by_object.setdefault(name, set()).add(owner)
    conflicts = {
        name: sorted(owners) for name, owners in owners_by_object.items() if len(owners) > 1
    }
    return conflicts


def conductor_layer_numbers_from_mapping(mapping_payload):
    layers = set()
    for row in mapping_payload.get("gds_import_layers", []):
        role = str(row.get("recommended_aedt_role") or "")
        destination = str(row.get("aedt_destination") or "")
        if role == "conductor" or destination.startswith("SCmetal"):
            layers.add(int(row["aedt_layer_number"]))
    if not layers:
        raise RuntimeError("Q2D marker assignment requires at least one conductor import layer")
    return layers


def transformed_marker_point(marker, rotations, modeler_units="um"):
    point = [um_to_modeler_units(value, modeler_units) for value in marker_source_point_um(marker)]
    for rotation in rotations:
        point = rotate_point_3d(point, rotation["axis"], float(rotation["angle_deg"]))
    return point


def um_to_modeler_units(value, modeler_units="um"):
    units = normalize_modeler_units(modeler_units)
    return value / AEDT_MODELER_UNIT_TO_UM[units]


def rotate_point_3d(point, axis, angle_deg):
    import math

    x, y, z = point
    angle = math.radians(angle_deg)
    c = math.cos(angle)
    s = math.sin(angle)
    if axis == "X":
        return [x, y * c - z * s, y * s + z * c]
    if axis == "Y":
        return [x * c + z * s, y, -x * s + z * c]
    if axis == "Z":
        return [x * c - y * s, x * s + y * c, z]
    raise RuntimeError(f"Unsupported rotation axis: {axis!r}")


def point_in_section_bbox(point, bbox, section_plane):
    if bbox is None or len(bbox) != 6:
        return False
    axes_by_plane = {
        "XY": (0, 1),
        "YZ": (1, 2),
        "ZX": (2, 0),
    }
    axes = axes_by_plane.get(section_plane, (0, 1))
    tolerance = 1e-3
    for axis in axes:
        if point[axis] < min(bbox[axis], bbox[axis + 3]) - tolerance:
            return False
        if point[axis] > max(bbox[axis], bbox[axis + 3]) + tolerance:
            return False
    return True


def q2d_conductor_type_for_aedt(conductor_type):
    mapping = {
        "Signal Line": "SignalLine",
        "Reference Ground": "ReferenceGround",
        "Non Ideal Ground": "NonIdealGround",
        "Floating Line": "FloatingLine",
        "Surface Ground": "SurfaceGround",
    }
    return mapping.get(conductor_type, conductor_type.replace(" ", ""))


def create_q2d_setup(q2d, recipe):
    setup_name = recipe.get("setup_name", "Setup1")
    setup = get_setup_by_name(q2d, setup_name)
    if setup is not None and ("CGDataBlock" not in setup.props or "RLDataBlock" not in setup.props):
        delete_existing_setup(q2d, setup_name)
        setup = None
    if setup is None:
        setup = q2d.create_setup(name=setup_name)
    props = q2d_setup_props(recipe)
    setup.props["AdaptiveFreq"] = props["AdaptiveFreq"]
    setup.props["Enabled"] = props["Enabled"]
    setup.props["SaveFields"] = props["SaveFields"]
    setup.props["CGDataBlock"].update(props["CGDataBlock"])
    setup.props["RLDataBlock"].update(props["RLDataBlock"])
    setup.update()
    return setup


def q2d_setup_props(recipe):
    settings = recipe.get("q2d_setup") or {}
    return {
        "AdaptiveFreq": str(settings.get("adaptive_frequency") or "6GHz"),
        "Enabled": bool(settings.get("enabled", True)),
        "SaveFields": bool(settings.get("save_fields", True)),
        "CGDataBlock": q2d_convergence_block_props(settings.get("cg") or {}, "CG"),
        "RLDataBlock": q2d_convergence_block_props(settings.get("rl") or {}, "RL"),
    }


def q2d_convergence_block_props(settings, data_type):
    return {
        "MaxPass": int(settings.get("max_pass", 99)),
        "MinPass": int(settings.get("min_pass", 1)),
        "MinConvPass": int(settings.get("min_converged_pass", 2)),
        "PerError": float(settings.get("percent_error", 0.01)),
        "PerRefine": float(settings.get("percent_refinement", 30)),
        "DataType": data_type,
        "Included": True,
        "UseParamConv": bool(settings.get("use_parameter_convergence", False)),
        "UseLossyParamConv": bool(settings.get("use_lossy_parameter_convergence", False)),
        "PerErrorParamConv": float(settings.get("parameter_convergence_percent_error", 1)),
        "UseLossConv": bool(settings.get("use_loss_convergence", False)),
    }


def setup_summary(recipe, setup):
    return {
        "requested": q2d_setup_props(recipe),
        "props": {
            "AdaptiveFreq": setup.props.get("AdaptiveFreq"),
            "CGDataBlock": dict(setup.props.get("CGDataBlock", {})),
            "RLDataBlock": dict(setup.props.get("RLDataBlock", {})),
        },
    }


def export_q3d_matrices(app, recipe, result_dir):
    exports = []
    for problem_type in recipe.get("matrix_problem_types", ("C", "AC RL")):
        for matrix_type in recipe.get("matrix_types", ("Maxwell", "Couple")):
            exports.append(
                export_matrix_data_checked(
                    app,
                    result_dir,
                    setup=recipe.get("setup_name", "Setup1"),
                    requested_problem_type=problem_type,
                    pyaedt_problem_type=problem_type,
                    matrix_type=matrix_type,
                )
            )
    return exports


def export_q2d_matrices(app, recipe, result_dir):
    exports = []
    for problem_type in recipe.get("matrix_problem_types", ("CG", "RL")):
        pyaedt_problem_type = q2d_pyaedt_problem_type(problem_type)
        for matrix_type in recipe.get("matrix_types", ("Maxwell", "Couple")):
            exports.append(
                export_matrix_data_checked(
                    app,
                    result_dir,
                    setup=recipe.get("setup_name", "Setup1"),
                    requested_problem_type=problem_type,
                    pyaedt_problem_type=pyaedt_problem_type,
                    matrix_type=matrix_type,
                    frequency_expression=q2d_adaptive_frequency(recipe),
                )
            )
    return exports


def q2d_pyaedt_problem_type(problem_type):
    text = str(problem_type)
    allowed = {"CG", "RL"}
    if text not in allowed:
        raise RuntimeError(
            "Unsupported Q2D matrix problem type: "
            f"{problem_type}. Regenerate the package with matrix_problem_types using CG/RL."
        )
    return text


def matrix_file_stem(problem_type, matrix_type):
    return f"{str(problem_type).lower().replace(' ', '_')}_{str(matrix_type).lower()}"


def export_matrix_data_checked(
    app,
    result_dir,
    *,
    setup,
    requested_problem_type,
    pyaedt_problem_type,
    matrix_type,
    sweep=None,
    file_prefix=None,
    frequency_expression=None,
):
    stem = matrix_file_stem(requested_problem_type, matrix_type)
    file_name = result_dir / f"{stem}_matrix.csv"
    if file_prefix:
        file_name = result_dir / f"{safe_filename(file_prefix)}_{stem}_matrix.csv"
    export_kwargs = {}
    if sweep is not None:
        export_kwargs["sweep"] = sweep
    if frequency_expression is not None:
        frequency, frequency_kwargs = q2d_matrix_frequency_export_kwargs(frequency_expression)
        export_kwargs.update(frequency_kwargs)
        ok, export_details = export_q2d_matrix_data_direct(
            app,
            file_name,
            problem_type=pyaedt_problem_type,
            matrix_type=matrix_type,
            setup=setup,
            sweep=sweep,
            frequency_hz=frequency_kwargs["freq_hz"],
        )
    else:
        frequency = parse_aedt_frequency_expression(frequency_expression)
        ok = app.export_matrix_data(
            file_name=str(file_name),
            problem_type=pyaedt_problem_type,
            matrix_type=matrix_type,
            setup=setup,
            **export_kwargs,
        )
        export_details = {"direct_odesign_export": False}
    record = {
        "requested_problem_type": requested_problem_type,
        "pyaedt_problem_type": pyaedt_problem_type,
        "matrix_type": matrix_type,
        "sweep": sweep,
        "frequency": frequency,
        "pyaedt_export_kwargs": dict(export_kwargs),
        "aedt_export_details": dict(export_details),
        "file_name": str(file_name),
        "return_value": bool(ok),
    }
    if not ok:
        raise RuntimeError(f"AEDT matrix export failed: {record}")
    if not file_name.is_file():
        raise RuntimeError(f"AEDT matrix export did not create file: {file_name}")
    if file_name.stat().st_size <= 0:
        raise RuntimeError(f"AEDT matrix export created an empty file: {file_name}")
    record["file_size"] = file_name.stat().st_size
    return record


def q2d_expected_export_records(recipe):
    records = []
    for problem_type in recipe.get("matrix_problem_types", ("CG", "RL")):
        for matrix_type in recipe.get("matrix_types", ("Maxwell", "Couple")):
            records.append(
                {
                    "problem_type": problem_type,
                    "matrix_type": matrix_type,
                    "file_name": f"{matrix_file_stem(problem_type, matrix_type)}_matrix.csv",
                }
            )
    return records


def q2d_solve_completion_status(result_dir, log_dir, recipe):
    expected_exports = q2d_expected_export_records(recipe)
    missing_exports = []
    for record in expected_exports:
        path = result_dir / record["file_name"]
        if not path.is_file() or path.stat().st_size <= 0:
            missing_exports.append(record["file_name"])

    workflow_state = read_json(log_dir / "q2d_workflow_state.json") or {}
    workflow_state_exists = bool(workflow_state)
    current_recipe_settings_hash = sha256_text(stable_json(q2d_recipe_settings(recipe)))
    previous_recipe_settings_hash = (
        workflow_state.get("recipe_settings_hash") if isinstance(workflow_state, dict) else None
    )
    recipe_settings_stale = bool(
        workflow_state_exists and previous_recipe_settings_hash != current_recipe_settings_hash
    )
    metadata = read_json(result_dir / "simulation_metadata.json") or {}
    solve_status = metadata.get("solve_status") if isinstance(metadata, dict) else {}
    analyze_setup = solve_status.get("analyze_setup") if isinstance(solve_status, dict) else None
    analyze_ok = bool(analyze_setup and analyze_setup.get("return_value"))
    failure_exists = (log_dir / "failure.json").is_file()
    if recipe_settings_stale:
        completion_status = "stale"
    elif analyze_ok and not missing_exports:
        completion_status = "complete"
    elif failure_exists:
        completion_status = "failed"
    else:
        completion_status = "incomplete"
    return {
        "completion_status": completion_status,
        "analyze_setup_ok": analyze_ok,
        "expected_exports": expected_exports,
        "missing_required_exports": missing_exports,
        "simulation_metadata_exists": bool(metadata),
        "failure_exists": failure_exists,
        "workflow_state_exists": workflow_state_exists,
        "recipe_settings_hash": current_recipe_settings_hash,
        "previous_recipe_settings_hash": previous_recipe_settings_hash,
        "recipe_settings_stale": recipe_settings_stale,
    }


def run_package(manifest, manifest_path, args):
    package_root = manifest_path.parent
    output_roots = resolve_output_roots(args, package_root)
    results_root = output_roots["results_root"]
    logs_root = output_roots["logs_root"]
    root_log_dir = run_log_root(args, logs_root)
    create_aedt_session(args, manifest)
    preflight = preflight_payload(args, manifest, output_roots)
    write_preflight(root_log_dir, preflight)
    if preflight.get("version_check_status") == "failed":
        write_json(
            root_log_dir / "failure.json",
            {
                "error": "AEDT version preflight failed",
                "version_check_errors": preflight.get("version_check_errors", []),
            },
        )
        raise RuntimeError(
            f"AEDT version preflight failed: {preflight.get('version_check_errors', [])}"
        )
    summary_rows = []
    package_failed = False
    try:
        for case, recipes in selected_manifest_cases(manifest, args):
            for recipe in recipes:
                result_dir = results_root / case["id"] / recipe["id"]
                log_dir = logs_root / case["id"] / recipe["id"]
                args._aedt_log_dirs.append(log_dir)
                row_started_at = time.monotonic()
                skip_status = should_skip_recipe_for_resume(
                    result_dir, log_dir, recipe, args, q2d_solve_completion_status
                )
                if skip_status is not None:
                    summary_rows.append(
                        {
                            "case_id": case["id"],
                            "point_slug": case["id"],
                            "recipe_id": recipe["id"],
                            "recipe_type": recipe["type"],
                            "status": "skipped",
                            "skip_reason": skip_status.get("skip_reason"),
                            "completion_status": skip_status.get("completion_status"),
                            "result_dir": str(result_dir),
                            "log_dir": str(log_dir),
                            "elapsed_seconds": 0.0,
                        }
                    )
                    log(log_dir, f"Skipping completed {case['id']} / {recipe['id']}")
                    continue
                try:
                    log(log_dir, f"Running {case['id']} / {recipe['id']} ({recipe['type']})")
                    RECIPE_DISPATCH[recipe["type"]](
                        case,
                        recipe,
                        manifest,
                        package_root,
                        result_dir,
                        log_dir,
                        args,
                    )
                    completion = (
                        q2d_solve_completion_status(result_dir, log_dir, recipe)
                        if recipe["type"] == "q2d_extraction" and args.mode == "solve"
                        else {"completion_status": f"{args.mode}_complete"}
                    )
                    summary_rows.append(
                        {
                            "case_id": case["id"],
                            "point_slug": case["id"],
                            "recipe_id": recipe["id"],
                            "recipe_type": recipe["type"],
                            "status": "complete",
                            "completion_status": completion.get("completion_status"),
                            "result_dir": str(result_dir),
                            "log_dir": str(log_dir),
                            "elapsed_seconds": time.monotonic() - row_started_at,
                        }
                    )
                except Exception:
                    failure = {"traceback": traceback.format_exc()}
                    aedt_messages = collect_recent_aedt_messages(args)
                    if aedt_messages:
                        failure["aedt_messages"] = aedt_messages
                    write_json(
                        log_dir / "failure.json",
                        failure,
                    )
                    summary_rows.append(
                        {
                            "case_id": case["id"],
                            "point_slug": case["id"],
                            "recipe_id": recipe["id"],
                            "recipe_type": recipe["type"],
                            "status": "failed",
                            "failure_kind": "exception",
                            "result_dir": str(result_dir),
                            "log_dir": str(log_dir),
                            "elapsed_seconds": time.monotonic() - row_started_at,
                        }
                    )
                    package_failed = True
                    if not args.continue_on_failure:
                        raise
        write_json(
            root_log_dir / "aedt_run_summary.json",
            {
                "schema_version": "aedt-run-summary.v1",
                "mode": args.mode,
                "resume_policy": args.resume_policy,
                "rows": summary_rows,
            },
        )
        if package_failed:
            raise RuntimeError("One or more AEDT package cases failed")
    finally:
        if summary_rows:
            write_json(
                root_log_dir / "aedt_run_summary.json",
                {
                    "schema_version": "aedt-run-summary.v1",
                    "mode": args.mode,
                    "resume_policy": args.resume_policy,
                    "rows": summary_rows,
                },
            )
        if sys.exc_info()[0] is KeyboardInterrupt:
            write_json(root_log_dir / "abort.json", {"event": "keyboard_interrupt"})
            stop_aedt_simulations(args, root_log_dir)
        finalize_aedt_session(args, root_log_dir, manifest, logger=log)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        default=str(Path(__file__).resolve().parents[2] / "manifest.yaml"),
    )
    parser.add_argument("--mode", choices=("import", "solve"), default=None)
    parser.add_argument(
        "--import",
        dest="import_mode",
        action="store_true",
        help="Convenience alias for --mode import.",
    )
    parser.add_argument(
        "--solve",
        dest="solve_mode",
        action="store_true",
        help="Convenience alias for --mode solve.",
    )
    parser.add_argument(
        "--case-id",
        action="append",
        default=[],
        help="Run only the selected manifest case id. May be repeated.",
    )
    parser.add_argument(
        "--recipe-id",
        action="append",
        default=[],
        help="Run only the selected recipe id. May be repeated.",
    )
    parser.add_argument(
        "--resume-policy",
        choices=("run_all", "skip_completed_retry_failed", "skip_completed_fail_failed"),
        default="run_all",
        help="Point-local resume policy for solve mode.",
    )
    parser.add_argument(
        "--skip-completed",
        action="store_true",
        default=False,
        help="Skip completed Q2D solve/export points in solve mode.",
    )
    parser.add_argument(
        "--no-skip-completed",
        dest="skip_completed",
        action="store_false",
        help="Disable skip-completed even when the loaded run config enables it.",
    )
    parser.add_argument(
        "--continue-on-failure",
        action="store_true",
        default=False,
        help="Continue running selected cases after a case failure and exit nonzero at the end.",
    )
    parser.add_argument(
        "--stop-on-failure",
        dest="continue_on_failure",
        action="store_false",
        help="Stop at the first case failure even when the loaded run config enables continuing.",
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        default=False,
        help=(
            "Run selected Q2D points in isolated worker AEDT projects. "
            "Applies to import and solve modes."
        ),
    )
    parser.add_argument(
        "--no-parallel",
        dest="parallel",
        action="store_false",
        help="Disable parallel worker mode even when the loaded run config enables it.",
    )
    parser.add_argument(
        "--progress",
        choices=("auto", "stream", "off"),
        default="auto",
        help="Display parent-side point progress for parallel import/solve runs.",
    )
    parser.add_argument(
        "--progress-interval-seconds",
        type=float,
        default=5.0,
        help="Seconds between parent-side parallel progress refreshes.",
    )
    parser.add_argument(
        "--worker-mode",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--abort-worker",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=None,
        help="Maximum number of parallel AEDT worker processes.",
    )
    parser.add_argument(
        "--num-cores",
        type=int,
        default=None,
        help="NumCores written to the AEDT HPC ACF for each worker.",
    )
    parser.add_argument(
        "--memory-mb-total",
        type=int,
        default=None,
        help="Total memory budget in MB used to derive AEDT worker RAMPercent.",
    )
    parser.add_argument(
        "--memory-mb-per-worker",
        type=int,
        default=None,
        help="Per-worker memory budget in MB used to derive AEDT worker RAMPercent.",
    )
    parser.add_argument(
        "--ram-percent",
        type=int,
        default=None,
        help="Explicit AEDT ACF RAMPercent override for each worker.",
    )
    parser.add_argument(
        "--core-budget",
        type=int,
        default=None,
        help="Maximum total logical cores available to AEDT workers.",
    )
    parser.add_argument(
        "--acf-file",
        default=None,
        help="Existing ANSYS HPC .acf file to pass to PyAEDT analyze_setup.",
    )
    parser.add_argument(
        "--worker-project-root",
        default=None,
        help="Directory where isolated worker .aedt projects are created.",
    )
    parser.add_argument(
        "--worker-log-root",
        default=None,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--non-graphical",
        dest="non_graphical",
        action="store_true",
        default=True,
        help="Run AEDT in non-graphical mode. This is the default.",
    )
    parser.add_argument(
        "--graphical",
        dest="non_graphical",
        action="store_false",
        help="Run AEDT with the graphical desktop visible.",
    )
    parser.add_argument(
        "--aedt-version",
        default=None,
        help="Optional AEDT version string passed to PyAEDT, for example 2024.2.",
    )
    parser.add_argument(
        "--grpc-port",
        type=int,
        default=None,
        help="Optional gRPC port passed to PyAEDT.",
    )
    parser.add_argument(
        "--grpc-insecure",
        dest="grpc_mode",
        action="store_const",
        const="insecure",
        default=None,
        help=("Disable PyAEDT secure gRPC mode before AEDT startup. This forces TCP InsecureMode."),
    )
    parser.add_argument(
        "--grpc-secure",
        dest="grpc_mode",
        action="store_const",
        const="secure",
        help="Use PyAEDT secure gRPC mode.",
    )
    parser.add_argument(
        "--grpc-auto",
        dest="grpc_mode",
        action="store_const",
        const="auto",
        help="Use the generated local-auto gRPC policy.",
    )
    parser.add_argument(
        "--grpc-local",
        choices=("true", "false"),
        default=None,
        help="Optionally set PyAEDT settings.grpc_local to true or false.",
    )
    parser.add_argument(
        "--new-desktop",
        dest="new_desktop",
        action="store_true",
        default=True,
        help="Start a new AEDT Desktop session for the first AEDT application.",
    )
    parser.add_argument(
        "--reuse-desktop",
        dest="new_desktop",
        action="store_false",
        help="Attach to an existing AEDT Desktop session when PyAEDT can find one.",
    )
    parser.add_argument(
        "--close-desktop",
        action="store_true",
        help="Ask PyAEDT to close the AEDT Desktop session on exit.",
    )
    parser.add_argument(
        "--force-rebuild",
        action="store_true",
        help="Clear recipe-owned AEDT geometry/setup before rebuilding incremental stages.",
    )
    parser.add_argument(
        "--results-root",
        default=None,
        help="Optional point-output root. Defaults to package-local points/.",
    )
    parser.add_argument(
        "--logs-root",
        default=None,
        help="Optional logs root. Defaults to package-local logs/.",
    )
    raw_args = sys.argv[1:]
    args = parser.parse_args(raw_args)
    if args.abort_worker:
        abort_worker_aedt_session(args)
        return
    manifest_path = Path(args.manifest).resolve()
    manifest = load_manifest(manifest_path)
    args = apply_run_config(args, manifest, manifest_path, raw_args)
    package_root = manifest_path.parent
    output_roots = resolve_output_roots(args, package_root)
    manifest = apply_worker_project_isolation(
        manifest,
        manifest_path,
        args,
        output_roots["results_root"],
    )
    try:
        if should_run_parallel_parent(args):
            run_point_local_sweep(
                manifest,
                manifest_path,
                args,
                resolve_hpc_resource=resolve_runtime_hpc_resource,
                completion_status=q2d_solve_completion_status,
                logger=log,
            )
            return
        run_package(manifest, manifest_path, args)
    except KeyboardInterrupt as exc:
        print("AEDT run aborted by user.", flush=True)
        raise SystemExit(130) from exc


if __name__ == "__main__":
    main()
