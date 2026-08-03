"""Point-local sweep and worker orchestration for generated AEDT packages.

This run-side module owns the parent process for one-script parallel AEDT runs:
it starts isolated worker subprocesses of ``run_aedt_native.py``, routes
per-point logs/results, applies resume policy, reports progress, and writes the
parent summary.

It also currently owns the small manifest-selection and run-log-root helpers
used by both serial and parallel paths. Those helpers stay here while the
runtime remains small; if they grow beyond sweep/run routing, they should move
to a narrower runtime context module. This module must not open PyAEDT apps,
mutate projects, or solve recipes. Workers do that through
``run_aedt_native.py`` and ``session.py``.
"""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
from collections import deque
from pathlib import Path

from .io import append_jsonl, read_json, resolve_output_roots, write_json

AEDT_WORKER_GRPC_PORT_BASE = 41000
AEDT_ABORT_GRACE_SECONDS = 60.0
WORKER_INTERRUPT_GRACE_SECONDS = 20.0
WORKER_TERM_GRACE_SECONDS = 3.0


def safe_filename(value):
    return "_".join(part for part in str(value).replace("\\", "/").split("/") if part)


def selected_manifest_cases(manifest, args):
    case_filter = set(args.case_id or [])
    recipe_filter = set(args.recipe_id or [])
    for case in manifest["cases"]:
        if case_filter and case["id"] not in case_filter:
            continue
        selected_recipes = [
            recipe
            for recipe in case["recipes"]
            if not recipe_filter or recipe["id"] in recipe_filter
        ]
        if selected_recipes:
            yield case, selected_recipes


def selected_manifest_pairs(manifest, args):
    for case, recipes in selected_manifest_cases(manifest, args):
        for recipe in recipes:
            yield case, recipe


def run_log_root(args, logs_root):
    worker_log_root = getattr(args, "worker_log_root", None)
    return Path(worker_log_root).resolve() if worker_log_root else logs_root


def worker_token(case_id, recipe_id):
    return safe_filename(f"{case_id}__{recipe_id}")


def default_worker_project_root(results_root):
    return Path(results_root)


def worker_project_path(args, manifest, manifest_path, case_id, recipe_id, results_root):
    token = worker_token(case_id, recipe_id)
    project_name = safe_filename(f"{manifest['project']['name']}__{token}")
    if args.worker_project_root:
        project_root = Path(args.worker_project_root).resolve()
        return project_root / case_id / "aedt_project" / f"{project_name}.aedt"
    return Path(results_root) / case_id / "aedt_project" / f"{project_name}.aedt"


def apply_worker_project_isolation(manifest, manifest_path, args, results_root):
    if not args.worker_mode:
        return manifest
    if len(args.case_id or []) != 1 or len(args.recipe_id or []) != 1:
        raise RuntimeError("--worker-mode requires exactly one --case-id and one --recipe-id")
    case_id = args.case_id[0]
    recipe_id = args.recipe_id[0]
    isolated_path = worker_project_path(
        args,
        manifest,
        manifest_path,
        case_id,
        recipe_id,
        results_root,
    )
    isolated_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = dict(manifest)
    manifest["project"] = dict(manifest["project"])
    manifest["project"]["canonical_path"] = manifest["project"]["path"]
    manifest["project"]["path"] = str(isolated_path)
    args._aedt_worker_project_path = str(isolated_path)
    return manifest


def should_run_parallel_parent(args):
    return bool(args.parallel and not args.worker_mode and args.mode in {"import", "solve"})


def resolve_parallel_max_workers(manifest, args, resolve_hpc_resource):
    resource = resolve_hpc_resource(manifest, args)
    max_workers = int(args.max_workers or resource["max_workers"])
    if max_workers < 1:
        raise RuntimeError("--max-workers must be >= 1")
    return max_workers


def is_tcp_port_free(port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", int(port)))
    except OSError:
        return False
    return True


def allocate_worker_ports(base_port, max_workers):
    base_port = int(base_port)
    max_workers = int(max_workers)
    scan_window = max(max_workers * 20, 256)
    scan_end = min(65535, base_port + scan_window - 1)
    ports = [port for port in range(base_port, scan_end + 1) if is_tcp_port_free(port)][
        :max_workers
    ]
    if len(ports) != max_workers:
        raise RuntimeError(
            "Not enough free AEDT gRPC ports: "
            f"base={base_port}, scanned={base_port}-{scan_end}, "
            f"required={max_workers}, found={len(ports)}"
        )
    return ports


def format_allocated_ports(ports):
    if not ports:
        return ""
    if ports == list(range(ports[0], ports[-1] + 1)):
        return f"{ports[0]}-{ports[-1]}" if len(ports) > 1 else str(ports[0])
    preview = ",".join(str(port) for port in ports[:8])
    return f"{preview},..." if len(ports) > 8 else preview


def parallel_worker_command(
    manifest_path,
    args,
    *,
    case,
    recipe,
    results_root,
    logs_root,
    worker_log_root,
    worker_project_root,
    worker_index=None,
    grpc_port=None,
):
    command = [
        sys.executable,
        str(Path(__file__).with_name("run_aedt_native.py").resolve()),
        "--manifest",
        str(manifest_path),
        "--mode",
        args.mode,
        "--worker-mode",
        "--case-id",
        case["id"],
        "--recipe-id",
        recipe["id"],
        "--results-root",
        str(results_root),
        "--logs-root",
        str(logs_root),
        "--worker-log-root",
        str(worker_log_root),
        "--resume-policy",
        args.resume_policy,
    ]
    if args.worker_project_root:
        command.extend(["--worker-project-root", str(worker_project_root)])
    if args.skip_completed:
        command.append("--skip-completed")
    if args.continue_on_failure:
        command.append("--continue-on-failure")
    if args.force_rebuild:
        command.append("--force-rebuild")
    if args.non_graphical:
        command.append("--non-graphical")
    else:
        command.append("--graphical")
    command.append("--close-desktop")
    if args.aedt_version:
        command.extend(["--aedt-version", str(args.aedt_version)])
    resolved_grpc_port = (
        grpc_port if grpc_port is not None else parallel_worker_grpc_port(args, worker_index)
    )
    if resolved_grpc_port is not None:
        command.extend(["--grpc-port", str(resolved_grpc_port)])
    if args.grpc_mode == "secure":
        command.append("--grpc-secure")
    elif args.grpc_mode == "insecure":
        command.append("--grpc-insecure")
    elif args.grpc_mode == "auto":
        command.append("--grpc-auto")
    if args.grpc_local is not None:
        command.extend(["--grpc-local", str(args.grpc_local)])
    if args.acf_file:
        command.extend(["--acf-file", str(args.acf_file)])
    for name, value in (
        ("--num-cores", args.num_cores),
        ("--max-workers", args.max_workers),
        ("--memory-mb-total", args.memory_mb_total),
        ("--memory-mb-per-worker", args.memory_mb_per_worker),
        ("--ram-percent", args.ram_percent),
        ("--core-budget", args.core_budget),
    ):
        if value is not None:
            command.extend([name, str(value)])
    return command


def parallel_worker_grpc_port(args, worker_index):
    if worker_index is None and args.grpc_port is None:
        return None
    base = int(args.grpc_port or AEDT_WORKER_GRPC_PORT_BASE)
    return base + int(worker_index or 0)


def start_worker_subprocess(command, stdout_path):
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stdout = stdout_path.open("w", encoding="utf-8")
    try:
        process = subprocess.Popen(
            command,
            stdout=stdout,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
    except Exception:
        stdout.close()
        raise
    return process, stdout


def wait_for_processes(processes, timeout_seconds):
    deadline = time.monotonic() + float(timeout_seconds)
    while time.monotonic() < deadline:
        if all(process.poll() is not None for process in processes):
            break
        time.sleep(0.1)


def signal_worker_process(process, sig):
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, sig)
    except ProcessLookupError:
        return
    except Exception:
        try:
            process.send_signal(sig)
        except Exception:
            pass


def process_group_exists(pgid):
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def cleanup_worker_process_group(process):
    for sig, timeout in (
        (signal.SIGTERM, WORKER_TERM_GRACE_SECONDS),
        (signal.SIGKILL, 1.0),
    ):
        if not process_group_exists(process.pid):
            return
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            return
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not process_group_exists(process.pid):
                return
            time.sleep(0.1)


def worker_abort_command(args, grpc_port):
    command = [
        sys.executable,
        str(Path(__file__).with_name("run_aedt_native.py").resolve()),
        "--abort-worker",
        "--grpc-port",
        str(grpc_port),
    ]
    if args.aedt_version:
        command.extend(["--aedt-version", str(args.aedt_version)])
    if args.grpc_mode == "secure":
        command.append("--grpc-secure")
    elif args.grpc_mode == "insecure":
        command.append("--grpc-insecure")
    elif args.grpc_mode == "auto":
        command.append("--grpc-auto")
    if args.grpc_local is not None:
        command.extend(["--grpc-local", str(args.grpc_local)])
    return command


class ParallelProgressReporter:
    def __init__(
        self,
        *,
        total,
        max_workers,
        mode,
        interval_seconds,
        log_path,
        axis_coverage=None,
        progress_paths=None,
    ):
        self.total = int(total)
        self.max_workers = int(max_workers)
        self.mode = str(mode or "auto")
        self.interval_seconds = float(interval_seconds)
        if self.interval_seconds <= 0:
            raise RuntimeError("--progress-interval-seconds must be > 0")
        self.log_path = Path(log_path)
        self.axis_coverage = list(axis_coverage or [])
        self.progress_paths = {
            str(key): Path(value) for key, value in dict(progress_paths or {}).items()
        }
        self.started_at = time.monotonic()
        self.queued = 0
        self.complete = 0
        self.failed = 0
        self.skipped = 0
        self.aborted = 0
        self.active = {}
        self._last_render = 0.0
        self._rendered_dynamic = False
        self._last_line_length = 0
        self._enabled = self.mode != "off"
        self._dynamic = self.mode == "auto" and sys.stdout.isatty()

    def start(self):
        self._write_event("started")
        if self._enabled:
            axis_text = format_parallel_axis_coverage(self.axis_coverage)
            if axis_text:
                print(f"AEDT sweep axes: {axis_text}", flush=True)
            self.render(force=True)

    def record_skipped(self, case_id, recipe_id, reason=None, *, render=True):
        self.skipped += 1
        self._write_event(
            "skipped",
            case_id=case_id,
            recipe_id=recipe_id,
            extra={"skip_reason": reason},
        )
        if render:
            self.render(force=True)

    def record_aborted(self, case_id, recipe_id, *, returncode=None, event=None, render=True):
        self.active.pop(f"{case_id}/{recipe_id}", None)
        self.aborted += 1
        self._write_event(
            event or "worker_closed_after_abort",
            case_id=case_id,
            recipe_id=recipe_id,
            extra={"returncode": returncode},
        )
        if render:
            self.render(force=True)

    def record_event(self, event, *, case_id=None, recipe_id=None, extra=None):
        self._write_event(event, case_id=case_id, recipe_id=recipe_id, extra=extra)

    def record_queued(self, case_id, recipe_id, progress_path=None, *, render=True):
        self.queued += 1
        if progress_path is not None:
            self.progress_paths[f"{case_id}/{recipe_id}"] = Path(progress_path)
        self._write_event("queued", case_id=case_id, recipe_id=recipe_id)
        if render:
            self.render(force=True)

    def record_started(self, case_id, recipe_id, worker_log_root=None):
        self.active[f"{case_id}/{recipe_id}"] = {
            "case_id": case_id,
            "recipe_id": recipe_id,
            "worker_log_root": None if worker_log_root is None else str(worker_log_root),
            "started_at": time.monotonic(),
        }
        self._write_event("worker_started", case_id=case_id, recipe_id=recipe_id)

    def record_completed(self, case_id, recipe_id, *, failed=False, returncode=None, render=True):
        self.active.pop(f"{case_id}/{recipe_id}", None)
        if failed:
            self.failed += 1
            event = "failed"
        else:
            self.complete += 1
            event = "completed"
        self._write_event(
            event,
            case_id=case_id,
            recipe_id=recipe_id,
            extra={"returncode": returncode},
        )
        if render:
            self.render(force=True)

    def maybe_render(self):
        if time.monotonic() - self._last_render >= self.interval_seconds:
            self.render(force=True)

    def finish(self):
        self._write_event("finished")
        self.render(force=True)
        if self._rendered_dynamic:
            print("", flush=True)

    def event_line(self, text):
        if self._rendered_dynamic:
            print("", flush=True)
            self._rendered_dynamic = False
            self._last_line_length = 0
        print(text, flush=True)

    def render(self, *, force=False):
        if not self._enabled:
            return
        now = time.monotonic()
        if not force and now - self._last_render < self.interval_seconds:
            return
        self._last_render = now
        line = format_parallel_progress_line(self.snapshot())
        if self._dynamic:
            print("\r" + line.ljust(self._last_line_length), end="", flush=True)
            self._last_line_length = len(line)
            self._rendered_dynamic = True
        else:
            print(line, flush=True)

    def snapshot(self):
        elapsed = time.monotonic() - self.started_at
        done = self.complete + self.failed + self.skipped
        remaining = max(self.total - done, 0)
        active = min(
            self.max_workers,
            max(self.total - self.skipped - self.complete - self.failed, 0),
        )
        eta = estimate_parallel_eta(
            elapsed,
            finished_work=self.complete + self.failed,
            remaining_work=max(self.total - self.skipped - self.complete - self.failed, 0),
        )
        return {
            "total": self.total,
            "done": done,
            "complete": self.complete,
            "failed": self.failed,
            "skipped": self.skipped,
            "aborted": self.aborted,
            "queued": self.queued,
            "active": len(self.active),
            "oldest_active_seconds": oldest_active_seconds(self.active.values()),
            "active_sample": active_worker_sample(self.active.values()),
            "pending": max(self.total - self.queued - self.skipped, 0),
            "remaining": remaining,
            "running_limit": active,
            "max_workers": self.max_workers,
            "elapsed_seconds": elapsed,
            "eta_seconds": eta,
            "stage_counts": parallel_stage_counts(self.active_progress_paths()),
        }

    def active_progress_paths(self):
        return {key: path for key, path in self.progress_paths.items() if key in self.active}

    def _write_event(self, event, *, case_id=None, recipe_id=None, extra=None):
        payload = {
            "schema_version": "aedt-parallel-progress.v1",
            "event": event,
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            **self.snapshot(),
        }
        if case_id is not None:
            payload["case_id"] = case_id
            payload["point_slug"] = case_id
        if recipe_id is not None:
            payload["recipe_id"] = recipe_id
        if self.axis_coverage:
            payload["axis_coverage"] = self.axis_coverage
        if extra:
            payload.update(extra)
        append_jsonl(self.log_path, payload)


def estimate_parallel_eta(elapsed_seconds, *, finished_work, remaining_work):
    if finished_work <= 0 or remaining_work <= 0:
        return None
    return elapsed_seconds / finished_work * remaining_work


def format_parallel_progress_line(snapshot):
    total = int(snapshot.get("total") or 0)
    done = int(snapshot.get("done") or 0)
    width = 20
    filled = 0 if total <= 0 else min(width, int(round(width * done / total)))
    bar = "#" * filled + "-" * (width - filled)
    stage_counts = snapshot.get("stage_counts") or {}
    stage_text = format_parallel_stage_counts(stage_counts)
    active = int(snapshot.get("active") or 0)
    max_workers = int(snapshot.get("max_workers") or snapshot.get("running_limit") or 0)
    launched = int(
        snapshot.get("queued")
        if snapshot.get("queued") is not None
        else snapshot.get("launched") or 0
    )
    pending = int(
        snapshot.get("pending") if snapshot.get("pending") is not None else max(total - launched, 0)
    )
    parts = [
        f"AEDT parallel [{bar}] done={done}/{total}",
        f"workers={active}/{max_workers}",
        f"launched={launched}",
        f"pending={pending}",
        f"failed={snapshot.get('failed', 0)}",
        f"elapsed={format_duration(snapshot.get('elapsed_seconds'))}",
        f"ETA={format_duration(snapshot.get('eta_seconds'))}",
    ]
    if snapshot.get("skipped", 0):
        parts.append(f"skipped={snapshot.get('skipped', 0)}")
    if snapshot.get("oldest_active_seconds") is not None:
        parts.append(f"oldest={format_duration(snapshot.get('oldest_active_seconds'))}")
    if snapshot.get("active_sample"):
        parts.append(f"sample={snapshot['active_sample']}")
    if stage_text:
        parts.append(f"stages={stage_text}")
    return " | ".join(parts)


def format_parallel_stage_counts(stage_counts):
    if not stage_counts:
        return ""
    return ", ".join(f"{stage}:{count}" for stage, count in sorted(stage_counts.items()))


def format_duration(seconds):
    if seconds is None:
        return "unknown"
    seconds = max(float(seconds), 0.0)
    minutes, sec = divmod(int(round(seconds)), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h{minutes:02d}m"
    if minutes:
        return f"{minutes}m{sec:02d}s"
    return f"{sec}s"


def oldest_active_seconds(active_workers):
    oldest = None
    now = time.monotonic()
    for worker in active_workers:
        started_at = worker.get("started_at")
        if started_at is None:
            continue
        age = max(now - float(started_at), 0.0)
        oldest = age if oldest is None else max(oldest, age)
    return oldest


def active_worker_sample(active_workers):
    workers = sorted(active_workers, key=lambda item: item.get("started_at", 0.0))
    if not workers:
        return ""
    return shorten_token(workers[0].get("case_id", ""))


def shorten_token(value, limit=54):
    text = str(value)
    if len(text) <= limit:
        return text
    return f"{text[: limit // 2]}...{text[-limit // 2 :]}"


def parallel_stage_counts(progress_paths):
    counts = {}
    for path in progress_paths.values():
        row = latest_jsonl_row(path)
        if not row:
            continue
        event = str(row.get("event") or "")
        if event in {"finished", "failed"}:
            continue
        stage = str(row.get("stage") or "unknown")
        counts[stage] = counts.get(stage, 0) + 1
    return counts


def latest_jsonl_row(path):
    path = Path(path)
    if not path.is_file():
        return None
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def parallel_axis_coverage(manifest, package_root, pairs):
    records = {}
    cases_by_id = {case.get("id"): case for case in manifest.get("cases", [])}
    payload = read_json(Path(package_root) / "points.json") or {}
    points = payload.get("points") if isinstance(payload, dict) else []
    parameters_by_slug = {
        point.get("point_slug"): {
            key.removeprefix("parameter_"): value
            for key, value in point.items()
            if key.startswith("parameter_") and key != "parameter_id"
        }
        for point in points
        if isinstance(point, dict) and point.get("point_slug")
    }
    for case, _recipe in pairs:
        case_row = cases_by_id.get(case.get("id"), case)
        parameters = parameters_by_slug.get(case_row.get("id"), {})
        for key, value in parameters.items():
            axis = key if str(key).startswith("parameter_") else f"parameter_{key}"
            records.setdefault(axis, set()).add(parallel_axis_value_token(value))
    return [
        {
            "axis": axis,
            "unique_count": len(values),
            "values_preview": sorted(str(value) for value in values)[:8],
        }
        for axis, values in sorted(records.items())
    ]


def parallel_axis_value_token(value):
    if isinstance(value, (dict, list, tuple)):
        try:
            return json.dumps(value, sort_keys=True)
        except TypeError:
            return str(value)
    return value


def format_parallel_axis_coverage(axis_coverage):
    return ", ".join(
        f"{record['axis']}={record['unique_count']} values"
        for record in axis_coverage
        if record.get("unique_count", 0) > 1
    )


def run_point_local_sweep(
    manifest=None,
    manifest_path=None,
    args=None,
    *,
    resolve_hpc_resource=None,
    completion_status=None,
    logger=None,
):
    if any(
        value is None
        for value in (
            manifest,
            manifest_path,
            args,
            resolve_hpc_resource,
            completion_status,
            logger,
        )
    ):
        raise NotImplementedError(
            "AEDT point-local sweep requires manifest, args, and runtime callbacks"
        )
    package_root = manifest_path.parent
    output_roots = resolve_output_roots(args, package_root)
    results_root = output_roots["results_root"]
    logs_root = output_roots["logs_root"]
    parent_log_root = run_log_root(args, logs_root)
    parent_log_root.mkdir(parents=True, exist_ok=True)
    max_workers = resolve_parallel_max_workers(manifest, args, resolve_hpc_resource)
    worker_project_root = (
        Path(args.worker_project_root).resolve()
        if args.worker_project_root
        else default_worker_project_root(results_root)
    )
    selected_pairs = list(selected_manifest_pairs(manifest, args))
    axis_coverage = parallel_axis_coverage(manifest, package_root, selected_pairs)
    resource = resolve_hpc_resource(manifest, args)
    preflight_payload = {
        "schema_version": "aedt-parallel-preflight.v1",
        "mode": args.mode,
        "max_workers": max_workers,
        "selected_point_count": len(selected_pairs),
        "worker_project_root": str(worker_project_root),
        "worker_project_default": (
            "points/<point_slug>/aedt_project/<project>.aedt"
            if not args.worker_project_root
            else None
        ),
        "resource": resource,
        "project_concurrency": "isolated_worker_projects",
        "progress": {
            "mode": args.progress,
            "interval_seconds": args.progress_interval_seconds,
            "axis_coverage": axis_coverage,
        },
    }
    progress = ParallelProgressReporter(
        total=len(selected_pairs),
        max_workers=max_workers,
        mode=args.progress,
        interval_seconds=args.progress_interval_seconds,
        log_path=parent_log_root / "parallel_progress.jsonl",
        axis_coverage=axis_coverage,
    )
    progress.start()

    pending = []
    summary_rows = []
    for case, recipe in selected_pairs:
        if recipe.get("type") != "q2d_extraction":
            raise RuntimeError(
                "Parallel AEDT worker mode currently supports q2d_extraction recipes only"
            )
        result_dir = results_root / case["id"] / recipe["id"]
        log_dir = logs_root / case["id"] / recipe["id"]
        worker_project = worker_project_path(
            args,
            manifest,
            manifest_path,
            case["id"],
            recipe["id"],
            results_root,
        )
        skip_status = should_skip_recipe_for_resume(
            result_dir,
            log_dir,
            recipe,
            args,
            completion_status,
            worker_project=worker_project,
        )
        if skip_status is not None:
            row = {
                "case_id": case["id"],
                "point_slug": case["id"],
                "recipe_id": recipe["id"],
                "recipe_type": recipe["type"],
                "status": "skipped",
                "skip_reason": skip_status.get("skip_reason"),
                "completion_status": skip_status.get("completion_status"),
                "result_dir": str(result_dir),
                "log_dir": str(log_dir),
                "worker_project_path": str(worker_project),
                "worker_project_exists": worker_project.is_file(),
                "elapsed_seconds": 0.0,
            }
            summary_rows.append(row)
            logger(log_dir, f"Skipping completed {case['id']} / {recipe['id']}")
            progress.record_skipped(case["id"], recipe["id"], skip_status.get("skip_reason"))
            continue
        pending.append((case, recipe))

    grpc_port_base = int(args.grpc_port or AEDT_WORKER_GRPC_PORT_BASE)
    worker_slot_count = min(max_workers, len(pending))
    worker_ports = (
        allocate_worker_ports(grpc_port_base, worker_slot_count) if worker_slot_count else []
    )
    write_json(
        parent_log_root / "aedt_parallel_preflight.json",
        {
            **preflight_payload,
            "pending_point_count": len(pending),
            "skipped_point_count": len(selected_pairs) - len(pending),
            "grpc_port_base": grpc_port_base,
            "grpc_ports": worker_ports,
            "grpc_port_scan_window": max(worker_slot_count * 20, 256) if worker_slot_count else 0,
        },
    )
    if worker_ports:
        progress.event_line(
            "AEDT gRPC ports: "
            f"base={grpc_port_base} "
            f"allocated={format_allocated_ports(worker_ports)} "
            f"workers={len(worker_ports)}"
        )

    active = {}
    available_worker_slots = deque(enumerate(worker_ports))
    next_pending_index = 0
    package_failed = False
    abort_requested = False
    force_requested = False

    def submit_worker(slot_index, grpc_port, case, recipe):
        token = worker_token(case["id"], recipe["id"])
        worker_log_root = logs_root / "workers" / token
        command = parallel_worker_command(
            manifest_path,
            args,
            case=case,
            recipe=recipe,
            results_root=results_root,
            logs_root=logs_root,
            worker_log_root=worker_log_root,
            worker_project_root=worker_project_root,
            grpc_port=grpc_port,
        )
        stdout_path = worker_log_root / "worker_stdout.log"
        worker_project = worker_project_path(
            args,
            manifest,
            manifest_path,
            case["id"],
            recipe["id"],
            results_root,
        )
        write_json(
            worker_log_root / "worker_command.json",
            {
                "case_id": case["id"],
                "recipe_id": recipe["id"],
                "command": command,
                "worker_slot_index": slot_index,
                "grpc_port": grpc_port,
                "worker_project_path": str(worker_project),
            },
        )
        process, stdout = start_worker_subprocess(command, stdout_path)
        worker = {
            "case": case,
            "recipe": recipe,
            "worker_log_root": worker_log_root,
            "stdout_path": stdout_path,
            "stdout": stdout,
            "process": process,
            "slot_index": slot_index,
            "grpc_port": grpc_port,
            "worker_project": worker_project,
            "started_at": time.monotonic(),
            "abort_requested": False,
        }
        active[process.pid] = worker
        progress.record_queued(
            case["id"],
            recipe["id"],
            logs_root / case["id"] / recipe["id"] / "progress.jsonl",
            render=False,
        )
        progress.record_started(case["id"], recipe["id"], worker_log_root)

    def submit_ready_workers():
        nonlocal next_pending_index
        while (
            not abort_requested
            and len(active) < max_workers
            and available_worker_slots
            and next_pending_index < len(pending)
        ):
            case, recipe = pending[next_pending_index]
            slot_index, grpc_port = available_worker_slots.popleft()
            try:
                submit_worker(slot_index, grpc_port, case, recipe)
            except Exception:
                available_worker_slots.appendleft((slot_index, grpc_port))
                raise
            next_pending_index += 1

    def finish_worker(pid, worker, *, status_override=None, event=None):
        nonlocal package_failed
        active.pop(pid, None)
        worker["stdout"].close()
        cleanup_worker_process_group(worker["process"])
        available_worker_slots.append((worker["slot_index"], worker["grpc_port"]))
        case = worker["case"]
        recipe = worker["recipe"]
        returncode = worker["process"].poll()
        result_dir = results_root / case["id"] / recipe["id"]
        log_dir = logs_root / case["id"] / recipe["id"]
        worker_project = worker["worker_project"]
        elapsed = time.monotonic() - worker["started_at"]
        worker_result = {
            "returncode": returncode,
            "elapsed_seconds": elapsed,
            "stdout_log": str(worker["stdout_path"]),
        }
        if status_override == "aborted":
            completion = {"completion_status": "aborted"}
            status = "aborted"
        elif args.mode == "import":
            completion = {
                "completion_status": (
                    "import_complete"
                    if returncode == 0 and worker_project.is_file()
                    else "import_failed"
                ),
                "worker_project_exists": worker_project.is_file(),
            }
            status = (
                "complete"
                if returncode == 0 and completion["completion_status"] == "import_complete"
                else "failed"
            )
        else:
            completion = completion_status(result_dir, log_dir, recipe)
            status = (
                "complete"
                if returncode == 0 and completion.get("completion_status") == "complete"
                else "failed"
            )
        if status == "failed":
            package_failed = True
        summary_rows.append(
            {
                "case_id": case["id"],
                "point_slug": case["id"],
                "recipe_id": recipe["id"],
                "recipe_type": recipe["type"],
                "status": status,
                "completion_status": completion.get("completion_status"),
                "returncode": returncode,
                "result_dir": str(result_dir),
                "log_dir": str(log_dir),
                "worker_log_root": str(worker["worker_log_root"]),
                "worker_stdout_log": worker_result["stdout_log"],
                "worker_project_path": str(worker_project),
                "worker_project_exists": worker_project.is_file(),
                "elapsed_seconds": elapsed,
            }
        )
        if status == "aborted":
            progress.record_aborted(
                case["id"],
                recipe["id"],
                returncode=returncode,
                event=event,
                render=False,
            )
        else:
            progress.record_completed(
                case["id"],
                recipe["id"],
                failed=status == "failed",
                returncode=returncode,
                render=False,
            )
        if status == "failed":
            progress.event_line(
                f"AEDT worker failed: {case['id']} / {recipe['id']} returncode={returncode}"
            )

    def collect_finished_workers(*, aborting=False, force_event=None):
        for pid, worker in list(active.items()):
            if worker["process"].poll() is None:
                continue
            status_override = "aborted" if aborting and worker["abort_requested"] else None
            finish_worker(pid, worker, status_override=status_override, event=force_event)

    def send_aedt_abort_sidecars():
        sidecars = []
        for worker in list(active.values()):
            if worker["abort_requested"]:
                continue
            worker["abort_requested"] = True
            case = worker["case"]
            recipe = worker["recipe"]
            port = worker["grpc_port"]
            if port is None:
                progress.record_event(
                    "aedt_abort_failed",
                    case_id=case["id"],
                    recipe_id=recipe["id"],
                    extra={"error": "missing grpc_port"},
                )
                continue
            stdout_path = worker["worker_log_root"] / "aedt_abort_stdout.log"
            process, stdout = start_worker_subprocess(
                worker_abort_command(args, port),
                stdout_path,
            )
            sidecars.append((worker, process, stdout))
        deadline = time.monotonic() + 10.0
        while sidecars and time.monotonic() < deadline:
            if all(process.poll() is not None for _, process, _ in sidecars):
                break
            time.sleep(0.1)
        for worker, process, stdout in sidecars:
            if process.poll() is None:
                signal_worker_process(process, signal.SIGKILL)
            stdout.close()
            case = worker["case"]
            recipe = worker["recipe"]
            event = "aedt_abort_sent" if process.returncode == 0 else "aedt_abort_failed"
            progress.record_event(
                event,
                case_id=case["id"],
                recipe_id=recipe["id"],
                extra={
                    "grpc_port": worker["grpc_port"],
                    "returncode": process.returncode,
                },
            )
            if event == "aedt_abort_sent":
                progress.event_line(f"AEDT abort sent: {case['id']} port={worker['grpc_port']}")

    def force_terminate_active_workers():
        if not active:
            return
        progress.event_line(f"Force terminating {len(active)} stuck workers")
        for sig, timeout in (
            (signal.SIGINT, WORKER_INTERRUPT_GRACE_SECONDS),
            (signal.SIGTERM, WORKER_TERM_GRACE_SECONDS),
            (signal.SIGKILL, 1.0),
        ):
            stuck = [
                worker["process"] for worker in active.values() if worker["process"].poll() is None
            ]
            if not stuck:
                break
            for process in stuck:
                signal_worker_process(process, sig)
            wait_for_processes(stuck, timeout)
        for pid, worker in list(active.items()):
            finish_worker(
                pid,
                worker,
                status_override="aborted",
                event="worker_force_terminated",
            )

    try:
        submit_ready_workers()
        if pending:
            progress.event_line(
                f"Started {len(active)} of {len(pending)} AEDT workers | "
                f"workers={len(active)}/{max_workers}"
            )
        while active or next_pending_index < len(pending):
            try:
                collect_finished_workers()
                submit_ready_workers()
                progress.maybe_render()
                time.sleep(0.2)
            except KeyboardInterrupt:
                abort_requested = True
                progress.record_event(
                    "abort_requested",
                    extra={
                        "active_workers": len(active),
                        "not_started_count": len(pending) - next_pending_index,
                    },
                )
                progress.event_line(
                    f"Abort requested; stopping {len(active)} active AEDT simulations"
                )
                try:
                    send_aedt_abort_sidecars()
                    progress.event_line("Waiting for workers to save and close...")
                    deadline = time.monotonic() + AEDT_ABORT_GRACE_SECONDS
                    while active and time.monotonic() < deadline:
                        collect_finished_workers(aborting=True)
                        progress.maybe_render()
                        time.sleep(0.2)
                except KeyboardInterrupt:
                    force_requested = True
                if active or force_requested:
                    force_terminate_active_workers()
                break
    finally:
        if active:
            force_terminate_active_workers()
        progress.finish()

    run_status = "aborted" if abort_requested else "failed" if package_failed else "complete"
    counts = {
        "completed_count": sum(1 for row in summary_rows if row["status"] == "complete"),
        "failed_count": sum(1 for row in summary_rows if row["status"] == "failed"),
        "aborted_count": sum(1 for row in summary_rows if row["status"] == "aborted"),
        "skipped_count": sum(1 for row in summary_rows if row["status"] == "skipped"),
        "not_started_count": len(pending) - next_pending_index if abort_requested else 0,
    }
    summary = {
        "schema_version": "aedt-run-summary.v1",
        "mode": args.mode,
        "parallel": True,
        "run_status": run_status,
        "max_workers": max_workers,
        "resume_policy": args.resume_policy,
        **counts,
        "rows": sorted(
            summary_rows,
            key=lambda item: (item.get("case_id", ""), item.get("recipe_id", "")),
        ),
    }
    write_json(logs_root / "aedt_run_summary.json", summary)
    if abort_requested:
        raise KeyboardInterrupt
    if package_failed:
        raise RuntimeError("One or more parallel AEDT worker cases failed")


def should_skip_recipe_for_resume(
    result_dir,
    log_dir,
    recipe,
    args,
    completion_status,
    *,
    worker_project=None,
):
    policy = args.resume_policy
    if args.skip_completed:
        policy = "skip_completed_retry_failed"
    if policy == "run_all":
        return None
    if recipe.get("type") != "q2d_extraction":
        return None
    if args.mode == "import":
        worker_project = Path(worker_project) if worker_project is not None else None
        if worker_project is not None and worker_project.is_file():
            return {
                "completion_status": "import_complete",
                "worker_project_exists": True,
                "skip_reason": "import_project_exists",
            }
        failure_path = Path(log_dir) / "failure.json"
        if policy == "skip_completed_fail_failed" and failure_path.is_file():
            raise RuntimeError(f"Existing Q2D import failure found: {failure_path}")
        return None
    if args.mode != "solve":
        return None
    status = completion_status(result_dir, log_dir, recipe)
    if status["completion_status"] == "complete":
        return {**status, "skip_reason": "completed"}
    if policy == "skip_completed_fail_failed" and status["completion_status"] == "failed":
        raise RuntimeError(f"Existing Q2D failure found: {log_dir / 'failure.json'}")
    return None


__all__ = [
    "apply_worker_project_isolation",
    "run_log_root",
    "run_point_local_sweep",
    "selected_manifest_cases",
    "selected_manifest_pairs",
    "should_run_parallel_parent",
]
