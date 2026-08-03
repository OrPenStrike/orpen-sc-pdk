"""AEDT session lifecycle for generated runtime packages.

This run-side module is copied into AEDT handoff packages. It owns AEDT version
selection, gRPC settings, PyAEDT application registration, modeler-unit setup,
message collection, and final save/release audit. It does not dispatch solver
recipes or run point-local sweeps.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from .io import write_json

AEDT_MODELER_UNIT_TO_UM = {
    "nm": 0.001,
    "um": 1.0,
    "mm": 1000.0,
    "cm": 10000.0,
    "m": 1000000.0,
    "mil": 25.4,
    "in": 25400.0,
}
AEDT_MODELER_UNIT_ALIASES = {
    "micron": "um",
    "microns": "um",
    "meter": "m",
    "meters": "m",
}


def create_aedt_session(args: Any | None = None, manifest: dict[str, Any] | None = None) -> Any:
    """Prepare the run-side AEDT session state container.

    The runtime uses the parsed CLI namespace as the session state holder so
    solver code can register PyAEDT apps as they are opened. Desktop instances
    are created lazily by ``create_aedt_app`` and released by
    ``finalize_aedt_session``.

    Args:
        args: Parsed runtime CLI namespace.
        manifest: Loaded AEDT handoff manifest.

    Returns:
        The same ``args`` object with AEDT runtime fields populated.
    """

    if args is None or manifest is None:
        raise NotImplementedError("AEDT runtime session requires parsed args and manifest")
    configure_aedt_runtime(args, manifest)
    return args


def collect_aedt_messages_from_app(app):
    messages = []
    targets = [
        getattr(app, "desktop_class", None),
        getattr(app, "_desktop_class", None),
        app,
    ]
    seen = set()
    for target in targets:
        if target is None:
            continue
        odesktop = getattr(target, "odesktop", None)
        if odesktop is None:
            continue
        for level in (0, 1, 2, 3):
            try:
                raw_messages = odesktop.GetMessages("", "", level)
            except Exception:
                continue
            if raw_messages is None:
                continue
            if isinstance(raw_messages, str):
                raw_iterable = [raw_messages]
            else:
                try:
                    raw_iterable = list(raw_messages)
                except TypeError:
                    raw_iterable = [str(raw_messages)]
            for message in raw_iterable:
                text = str(message)
                if text not in seen:
                    seen.add(text)
                    messages.append(text)
    return messages


def collect_recent_aedt_messages(args):
    messages = []
    seen = set()
    for app in getattr(args, "_aedt_apps", []):
        for message in collect_aedt_messages_from_app(app):
            if message not in seen:
                seen.add(message)
                messages.append(message)
    return messages


def configure_aedt_runtime(args, manifest):
    from ansys.aedt.core.generic.settings import settings

    args._aedt_apps = []
    args._aedt_log_dirs = []
    runtime = manifest.get("runtime") or {}
    version_payload = resolve_aedt_version(args, runtime)
    grpc_payload = resolve_grpc_settings(args, runtime, version_payload)
    args.aedt_version = version_payload.get("selected_aedt_version")
    settings.grpc_secure_mode = bool(grpc_payload["grpc_secure_mode"])
    settings.grpc_local = bool(grpc_payload["grpc_local"])
    args._aedt_runtime_preflight = {
        **version_payload,
        **grpc_payload,
        "runtime_manifest": runtime,
    }


def parse_bool(value):
    return str(value).casefold() in {"1", "true", "yes", "on"}


def installed_aedt_versions_payload():
    try:
        from ansys.aedt.core.internal.aedt_versions import aedt_versions

        installed = dict(aedt_versions.installed_versions)
        current = aedt_versions.current_version or None
        latest = aedt_versions.latest_version or None
    except Exception as exc:
        return {
            "installed_aedt_versions": {},
            "detected_current_version": None,
            "detected_latest_version": None,
            "detection_error": repr(exc),
        }
    return {
        "installed_aedt_versions": installed,
        "detected_current_version": current,
        "detected_latest_version": latest,
        "detection_error": None,
    }


def resolve_aedt_version(args, runtime):
    detected = installed_aedt_versions_payload()
    installed = detected["installed_aedt_versions"]
    cli_version = args.aedt_version
    manifest_version = runtime.get("aedt_version")
    allowed_versions = list(runtime.get("allowed_aedt_versions") or [])
    selected = cli_version or manifest_version
    selection_source = "cli" if cli_version else "manifest" if manifest_version else "auto"
    if selected is None and allowed_versions and installed:
        selected = next((version for version in allowed_versions if version in installed), None)
        selection_source = "allowed_versions" if selected else "allowed_versions_missing"
    if selected is None:
        selected = detected.get("detected_current_version") or detected.get(
            "detected_latest_version"
        )
        selection_source = "detected" if selected else "unspecified"

    explicit_requirement = bool(cli_version or manifest_version or allowed_versions)
    version_policy = runtime.get("version_policy") or "auto"
    selected_install_path = installed.get(selected) if selected else None
    status = "ok"
    errors = []
    if allowed_versions and selected not in allowed_versions:
        status = "failed"
        errors.append(
            f"selected AEDT version {selected!r} is not in allowed versions {allowed_versions!r}"
        )
    if explicit_requirement and installed and selected not in installed:
        status = "failed"
        errors.append(
            f"selected AEDT version {selected!r} is not installed; installed={sorted(installed)}"
        )
    if explicit_requirement and not installed:
        status = "failed"
        errors.append("AEDT version was required but installed versions could not be detected")

    return {
        **detected,
        "aedt_version_cli": cli_version,
        "aedt_version_manifest": manifest_version,
        "allowed_aedt_versions": allowed_versions,
        "selected_aedt_version": selected,
        "selected_aedt_version_source": selection_source,
        "selected_aedt_install_path": selected_install_path,
        "version_policy": version_policy,
        "version_check_status": status,
        "version_check_errors": errors,
        "build_evidence": build_evidence(selected_install_path),
    }


def build_evidence(install_path):
    if not install_path:
        return {"status": "unknown", "files": []}
    root = Path(install_path)
    candidates = []
    for base in (root, root.parent):
        try:
            candidates.extend(sorted(base.glob("**/builddate.txt")))
        except Exception:
            pass
    files = []
    for path in candidates[:10]:
        try:
            files.append({"path": str(path), "text": path.read_text(errors="replace").strip()})
        except Exception as exc:
            files.append({"path": str(path), "error": repr(exc)})
    return {"status": "found" if files else "unknown", "files": files}


def resolve_grpc_settings(args, runtime, version_payload):
    requested = args.grpc_mode or runtime.get("grpc_mode") or "auto"
    if args.grpc_local is not None:
        grpc_local = parse_bool(args.grpc_local)
        grpc_local_source = "cli"
    elif runtime.get("grpc_local") is not None:
        grpc_local = bool(runtime["grpc_local"])
        grpc_local_source = "manifest"
    else:
        grpc_local = True
        grpc_local_source = "mode_default"
    if requested == "auto":
        resolved = "secure" if grpc_local else auto_nonlocal_grpc_mode(version_payload)
    else:
        resolved = requested
    return {
        "grpc_mode_requested": requested,
        "grpc_mode_resolved": resolved,
        "grpc_secure_mode": resolved == "secure",
        "grpc_local": grpc_local,
        "grpc_local_source": grpc_local_source,
        "grpc_decision_reason": grpc_decision_reason(requested, resolved, version_payload),
    }


def auto_nonlocal_grpc_mode(version_payload):
    if os.environ.get("ANSYS_GRPC_CERTIFICATES"):
        return "secure"
    return "secure" if grpc_secure_supported(version_payload) else "insecure"


def grpc_secure_supported(version_payload):
    version = version_payload.get("selected_aedt_version")
    if not version:
        return False
    try:
        major, release = [int(part) for part in str(version).split(".")[:2]]
    except Exception:
        return False
    if major >= 2026:
        return True
    return False


def grpc_decision_reason(requested, resolved, version_payload):
    if requested == resolved:
        return f"requested {requested}"
    return (
        "auto selected "
        f"{resolved} for AEDT {version_payload.get('selected_aedt_version') or 'unknown'}"
    )


def aedt_constructor_kwargs(args, *, new_desktop=None):
    kwargs = {
        "version": args.aedt_version,
        "non_graphical": args.non_graphical,
        "remove_lock": True,
    }
    if args.grpc_port is not None:
        kwargs["port"] = args.grpc_port
    if new_desktop is None:
        kwargs["new_desktop"] = args.new_desktop
    else:
        kwargs["new_desktop"] = new_desktop
    kwargs["close_on_exit"] = should_close_desktop(args)
    return kwargs


def create_aedt_app(app_class, args, **kwargs):
    app = app_class(**kwargs)
    register_aedt_app(args, app)
    return app


def register_aedt_app(args, app):
    apps = getattr(args, "_aedt_apps", None)
    if apps is not None:
        apps.append(app)


def should_close_desktop(args):
    return bool(args.close_desktop)


def recipe_modeler_units(recipe):
    return normalize_modeler_units(recipe.get("modeler_units") or "um")


def normalize_modeler_units(units):
    text = str(units or "").strip()
    if not text:
        raise RuntimeError("AEDT modeler_units must not be empty")
    normalized = AEDT_MODELER_UNIT_ALIASES.get(text.casefold(), text.casefold())
    if normalized not in AEDT_MODELER_UNIT_TO_UM:
        raise RuntimeError(
            f"AEDT modeler_units must be one of {sorted(AEDT_MODELER_UNIT_TO_UM)}; got {units!r}"
        )
    return normalized


def set_modeler_units(app, recipe):
    units = recipe_modeler_units(recipe)
    modeler = getattr(app, "modeler", None)
    if modeler is None:
        raise RuntimeError(
            f"{type(app).__name__} does not expose a modeler for unit setup; "
            f"cannot enforce modeler_units={units!r}"
        )
    try:
        app.modeler.model_units = units
    except Exception as exc:
        raise RuntimeError(
            f"{type(app).__name__} modeler units could not be set to {units!r}"
        ) from exc
    try:
        active_units = getattr(app.modeler, "model_units", None)
    except Exception:
        active_units = None
    if active_units and str(active_units).casefold() != units.casefold():
        raise RuntimeError(
            f"{type(app).__name__} modeler units expected {units!r}, got {active_units!r}"
        )
    return units


def ensure_design_modeler_units(app, recipe, solver_type):
    units = set_modeler_units(app, recipe)
    return {
        "solver_type": solver_type,
        "modeler_units": units,
        "design": getattr(app, "design_name", None),
    }


def app_label(app):
    try:
        project = getattr(app, "project_name", None)
    except Exception:
        project = None
    try:
        design = getattr(app, "design_name", None)
    except Exception:
        design = None
    return {
        "class": type(app).__name__,
        "project": project,
        "design": design,
    }


def app_desktop_key(app):
    desktop = getattr(app, "desktop_class", None) or getattr(app, "_desktop_class", None)
    return id(desktop) if desktop is not None else id(app)


def project_lock_path(manifest):
    return Path(str(manifest["project"]["path"]) + ".lock")


def stop_aedt_simulations(args, logs_root=None):
    apps = list(getattr(args, "_aedt_apps", []))
    payload = {"clean_stop": True, "stopped_apps": []}
    stopped_keys = set()
    for app in reversed(apps):
        desktop_key = app_desktop_key(app)
        if desktop_key in stopped_keys:
            continue
        stopped_keys.add(desktop_key)
        record = app_label(app)
        try:
            record["result"] = app.stop_simulations(clean_stop=True)
        except Exception as exc:
            record["result"] = False
            record["error"] = repr(exc)
        payload["stopped_apps"].append(record)
    if logs_root is not None:
        write_json(Path(logs_root) / "aedt_abort.json", payload)
    print("AEDT abort:", json.dumps(payload, indent=2), flush=True)
    return payload


def finalize_aedt_session(args, logs_root, manifest, *, logger=None):
    apps = list(getattr(args, "_aedt_apps", []))
    close_desktop = should_close_desktop(args)
    payload = {
        "close_desktop": close_desktop,
        "new_desktop": args.new_desktop,
        "app_count": len(apps),
        "saved_apps": [],
        "released_desktops": [],
    }
    for app in reversed(apps):
        record = app_label(app)
        try:
            record["result"] = bool(app.save_project())
        except Exception as exc:
            record["result"] = False
            record["error"] = repr(exc)
        payload["saved_apps"].append(record)

    released_keys = set()
    for app in reversed(apps):
        desktop_key = app_desktop_key(app)
        if desktop_key in released_keys:
            continue
        released_keys.add(desktop_key)
        record = app_label(app)
        try:
            record["result"] = bool(
                app.release_desktop(close_projects=True, close_desktop=close_desktop)
            )
        except Exception as exc:
            record["result"] = False
            record["error"] = repr(exc)
        payload["released_desktops"].append(record)

    lifecycle_errors = [
        record
        for record in (*payload["saved_apps"], *payload["released_desktops"])
        if not record.get("result")
    ]
    payload["lifecycle_status"] = "failed" if lifecycle_errors else "complete"
    if lifecycle_errors:
        payload["lifecycle_errors"] = lifecycle_errors

    lock_path = project_lock_path(manifest)
    payload["project_lock"] = str(lock_path)
    payload["project_lock_exists"] = lock_path.exists()
    write_json(logs_root / "aedt_lifecycle.json", payload)
    if logger is not None:
        for log_dir in getattr(args, "_aedt_log_dirs", []):
            logger(
                log_dir,
                (
                    "AEDT lifecycle: "
                    f"close_desktop={close_desktop} "
                    f"released={payload['released_desktops']} "
                    f"project_lock_exists={payload['project_lock_exists']}"
                ),
            )
    print("AEDT lifecycle:", json.dumps(payload, indent=2), flush=True)
    if lifecycle_errors and sys.exc_info()[0] is None:
        raise RuntimeError(f"AEDT lifecycle finalization failed: {lifecycle_errors}")
    return payload


__all__ = [
    "AEDT_MODELER_UNIT_TO_UM",
    "AEDT_MODELER_UNIT_ALIASES",
    "aedt_constructor_kwargs",
    "app_label",
    "collect_aedt_messages_from_app",
    "collect_recent_aedt_messages",
    "configure_aedt_runtime",
    "create_aedt_app",
    "create_aedt_session",
    "ensure_design_modeler_units",
    "finalize_aedt_session",
    "normalize_modeler_units",
    "recipe_modeler_units",
    "register_aedt_app",
    "set_modeler_units",
    "should_close_desktop",
    "stop_aedt_simulations",
]
