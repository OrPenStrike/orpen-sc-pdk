from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from textwrap import dedent
from typing import Any

import orpen_sc_pdk
from orpen_sc_pdk.cells import (
    cpw_straight,
    martinis2022_differential_ribbon_capacitor,
    resonator,
)
from orpen_sc_pdk.materials import get_gsim_material_overlay

DEFAULT_OUTPUT_DIR = Path("build/public-palace-smoke-evidence")
EVIDENCE_FILENAME = "public_palace_smoke_evidence.json"
PUBLIC_SLURM_PROFILE_CATALOG = (
    Path(__file__).resolve().parent / "fixtures" / "public_slurm_profiles.json"
)
PUBLIC_HELPER_NODE_INVENTORY = (
    Path(__file__).resolve().parent / "fixtures" / "public_simulation_helper_nodes.json"
)
PUBLIC_PROBLEM_NOTEBOOK_CROSSCHECK = (
    Path(__file__).resolve().parent / "fixtures" / "public_problem_notebook_crosscheck.json"
)
PUBLIC_SIMULATION_GOAL_AUDIT = (
    Path(__file__).resolve().parent / "fixtures" / "public_simulation_goal_audit.json"
)
PUBLIC_GSIM_BOUNDARY_REVIEW_CROSSCHECK = (
    Path(__file__).resolve().parent / "fixtures" / "public_gsim_boundary_review_crosscheck.json"
)
GSIM_BOUNDARY_REVIEW_COVERAGE_FILENAME = "public_gsim_boundary_review_coverage_evidence.json"
PUBLIC_INTERFACE_PRESET_REVIEW_QUEUE = (
    Path(__file__).resolve().parent / "fixtures" / "public_interface_preset_review_queue.json"
)
INTERFACE_PRESET_PROMOTION_GATE_FILENAME = "public_interface_preset_promotion_gate_evidence.json"
CAD_MESH_IDENTITY_HANDOFF_FILENAME = "public_cad_mesh_identity_handoff_evidence.json"
MESHWELL_HANDOFF_CONTRACT_GATE_FILENAME = "public_meshwell_handoff_contract_gate_evidence.json"
PUBLIC_CAD_MESH_IDENTITY_PROBLEM_KEYS = (
    "driven_cpw",
    "eigenmode_resonator",
    "electrostatic_same_layer_capacitor",
)
INTERFACE_PRESET_ROLES = ("MA", "MS", "SA")


def _default_gsim_repo_path() -> Path:
    return Path(__file__).resolve().parents[2] / "GDSFactory_Community_Workbench" / "gsim"


def _default_meshwell_repo_path() -> Path:
    return Path(__file__).resolve().parents[2] / "GDSFactory_Community_Workbench" / "meshwell"


def load_public_simulation_helper_node_inventory() -> list[dict[str, Any]]:
    """Load the public helper-node coverage matrix used by docs and evidence."""

    return json.loads(PUBLIC_HELPER_NODE_INVENTORY.read_text())


def load_public_problem_notebook_crosscheck() -> list[dict[str, Any]]:
    """Load the public/private notebook cross-check matrix."""

    return json.loads(PUBLIC_PROBLEM_NOTEBOOK_CROSSCHECK.read_text())


def load_public_simulation_goal_audit() -> list[dict[str, Any]]:
    """Load the public simulation migration goal audit matrix."""

    return json.loads(PUBLIC_SIMULATION_GOAL_AUDIT.read_text())


def load_public_gsim_boundary_review_crosscheck() -> list[dict[str, Any]]:
    """Load the local gsim branch boundary-review cross-check matrix."""

    return json.loads(PUBLIC_GSIM_BOUNDARY_REVIEW_CROSSCHECK.read_text())


def _run_git(repo: Path, args: Sequence[str]) -> list[str]:
    completed = subprocess.run(
        ["git", "-C", repo.as_posix(), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in completed.stdout.splitlines() if line]


def _first_existing_git_ref(repo: Path, refs: Sequence[str]) -> str | None:
    for ref in refs:
        try:
            _run_git(repo, ["rev-parse", "--verify", "--quiet", ref])
        except subprocess.CalledProcessError:
            continue
        return ref
    return None


def _local_gsim_commits(
    repo: Path,
    base_ref: str | None = None,
) -> tuple[str | None, list[dict[str, str]]]:
    resolved_base = base_ref or _first_existing_git_ref(repo, ("upstream/main", "origin/main"))
    if resolved_base is None:
        return None, []
    lines = _run_git(repo, ["rev-list", "--oneline", "--reverse", f"{resolved_base}..HEAD"])
    commits = []
    for line in lines:
        commit, _, summary = line.partition(" ")
        commits.append({"commit": commit, "summary": summary})
    return resolved_base, commits


def build_public_gsim_boundary_review_coverage_evidence(
    output_dir: str | Path = DEFAULT_OUTPUT_DIR / "gsim-boundary-review-coverage",
    *,
    gsim_repo: str | Path | None = None,
    base_ref: str | None = None,
    relative_to: str | Path | None = None,
) -> dict[str, Any]:
    """Build local gsim commit-to-boundary-review coverage evidence."""

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    relative_root = Path(relative_to) if relative_to is not None else None
    repo_path = Path(gsim_repo) if gsim_repo is not None else _default_gsim_repo_path()
    review_rows = load_public_gsim_boundary_review_crosscheck()
    reviewed_commits = [str(row["commit"]) for row in review_rows]
    duplicate_review_commits = sorted(
        commit for commit, count in _count_values(reviewed_commits).items() if count > 1
    )
    invalid_review_rows = [
        str(row.get("commit", ""))
        for row in review_rows
        if not str(row.get("review_status", "")).startswith("reviewed_")
        or not row.get("boundary_group")
        or not row.get("owner_surface")
        or ".md" not in str(row.get("evidence_anchor", ""))
    ]

    local_repo_status = "available" if (repo_path / ".git").exists() else "missing"
    resolved_base: str | None = None
    local_commits: list[dict[str, str]] = []
    git_error: str | None = None
    if local_repo_status == "available":
        try:
            resolved_base, local_commits = _local_gsim_commits(repo_path, base_ref)
        except subprocess.CalledProcessError as exc:
            local_repo_status = "git_error"
            git_error = exc.stderr.strip() or str(exc)
    gsim_branch = None
    gsim_head = None
    if local_repo_status == "available":
        try:
            gsim_branch = _run_git(repo_path, ["rev-parse", "--abbrev-ref", "HEAD"])[0]
            gsim_head = _run_git(repo_path, ["rev-parse", "--short", "HEAD"])[0]
        except (IndexError, subprocess.CalledProcessError) as exc:
            local_repo_status = "git_error"
            git_error = str(exc)

    local_commit_ids = [row["commit"] for row in local_commits]
    reviewed_set = set(reviewed_commits)
    local_set = set(local_commit_ids)
    missing_review_commits = [commit for commit in local_commit_ids if commit not in reviewed_set]
    stale_review_commits = [commit for commit in reviewed_commits if commit not in local_set]
    if local_repo_status != "available" or resolved_base is None:
        coverage_status = "not_checked"
    elif (
        missing_review_commits
        or stale_review_commits
        or duplicate_review_commits
        or invalid_review_rows
    ):
        coverage_status = "incomplete"
    else:
        coverage_status = "complete"

    review_by_commit = {str(row["commit"]): row for row in review_rows}
    coverage_rows = []
    for local_row in local_commits:
        commit = local_row["commit"]
        review = review_by_commit.get(commit, {})
        coverage_rows.append(
            {
                "commit": commit,
                "summary": local_row["summary"],
                "local_branch_status": "present",
                "review_status": review.get("review_status", "missing_review"),
                "boundary_group": review.get("boundary_group"),
                "ecosystem_home": review.get("ecosystem_home"),
                "owner_surface": review.get("owner_surface"),
                "evidence_anchor": review.get("evidence_anchor"),
            }
        )
    for commit in stale_review_commits:
        review = review_by_commit[commit]
        coverage_rows.append(
            {
                "commit": commit,
                "summary": review.get("summary"),
                "local_branch_status": "not_in_local_range",
                "review_status": review.get("review_status"),
                "boundary_group": review.get("boundary_group"),
                "ecosystem_home": review.get("ecosystem_home"),
                "owner_surface": review.get("owner_surface"),
                "evidence_anchor": review.get("evidence_anchor"),
            }
        )

    evidence_path = output_dir / GSIM_BOUNDARY_REVIEW_COVERAGE_FILENAME
    evidence = {
        "schema_version": 1,
        "workflow": "public-gsim-boundary-review-coverage",
        "repo": "orpen-sc-pdk",
        "local_gsim_repo": repo_path.as_posix(),
        "local_repo_status": local_repo_status,
        "gsim_branch": gsim_branch,
        "gsim_head": gsim_head,
        "base_ref": resolved_base,
        "first_commit": local_commit_ids[0] if local_commit_ids else None,
        "last_commit": local_commit_ids[-1] if local_commit_ids else None,
        "git_error": git_error,
        "coverage_status": coverage_status,
        "coverage_complete": coverage_status == "complete",
        "fixture_commit_count": len(reviewed_commits),
        "git_log_commit_count": len(local_commits),
        "reviewed_commit_count": len(reviewed_commits),
        "local_commit_count": len(local_commits),
        "covered_commit_count": sum(
            1 for row in coverage_rows if str(row["review_status"]).startswith("reviewed_")
        ),
        "missing_review_commits": missing_review_commits,
        "stale_review_commits": stale_review_commits,
        "missing_from_fixture": missing_review_commits,
        "extra_in_fixture": stale_review_commits,
        "duplicate_review_commits": duplicate_review_commits,
        "duplicate_fixture_commits": duplicate_review_commits,
        "invalid_review_rows": invalid_review_rows,
        "boundary_group_counts": _count_values([str(row["boundary_group"]) for row in review_rows]),
        "review_status_counts": _count_values([str(row["review_status"]) for row in review_rows]),
        "ecosystem_home_counts": _count_values([str(row["ecosystem_home"]) for row in review_rows]),
        "deferred_scope": [
            "Magnetostatic report contract",
            "real HPC/private profile validation",
        ],
        "owner_boundaries": {
            "gsim": (
                "reusable Palace simulation, config, manifest, runtime, and report-loader code"
            ),
            "orpen-sc-pdk": "publication-safe review evidence and notebook display",
        },
        "coverage_rows": coverage_rows,
    }
    evidence["output_dir"] = (
        _relative_path(output_dir, relative_root)
        if relative_root is not None
        else output_dir.as_posix()
    )
    evidence["evidence_path"] = (
        _relative_path(evidence_path, relative_root)
        if relative_root is not None
        else evidence_path.as_posix()
    )
    evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    return evidence


def public_gsim_boundary_review_coverage_table(
    output_dir: str | Path = DEFAULT_OUTPUT_DIR / "gsim-boundary-review-coverage",
) -> Any:
    """Return local gsim commit-to-boundary-review coverage rows."""

    import pandas as pd

    evidence = build_public_gsim_boundary_review_coverage_evidence(output_dir)
    columns = [
        "commit",
        "summary",
        "local_branch_status",
        "review_status",
        "boundary_group",
        "ecosystem_home",
        "evidence_anchor",
    ]
    return pd.DataFrame(evidence["coverage_rows"]).loc[:, columns]


def _source_contract_row(
    *,
    contract_item: str,
    owner_repo: str,
    repo_path: Path,
    relative_path: str,
    required_signals: Sequence[str],
    current_signal: str,
    remaining_gap: str,
    evidence_status: str = "covered_source",
) -> dict[str, Any]:
    source_path = repo_path / relative_path
    text = source_path.read_text() if source_path.is_file() else ""
    missing_signals = [signal for signal in required_signals if signal not in text]
    resolved_status = (
        evidence_status
        if source_path.is_file() and not missing_signals
        else "missing_source_signal"
    )
    return {
        "contract_item": contract_item,
        "owner_repo": owner_repo,
        "source_path": source_path.as_posix(),
        "relative_path": relative_path,
        "evidence_status": resolved_status,
        "required_signals": list(required_signals),
        "missing_signals": missing_signals,
        "current_signal": current_signal,
        "remaining_gap": remaining_gap,
    }


def _evidence_status_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    statuses = sorted({str(row["evidence_status"]) for row in rows})
    return {
        status: sum(str(row["evidence_status"]) == status for row in rows) for status in statuses
    }


def build_public_meshwell_handoff_contract_gate_evidence(
    output_dir: str | Path = DEFAULT_OUTPUT_DIR / "meshwell-handoff-contract-gate",
    *,
    meshwell_repo: str | Path | None = None,
    gsim_repo: str | Path | None = None,
    relative_to: str | Path | None = None,
) -> dict[str, Any]:
    """Build meshwell-to-gsim physical-name handoff contract gate evidence."""

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    relative_root = Path(relative_to) if relative_to is not None else None
    meshwell_path = (
        Path(meshwell_repo) if meshwell_repo is not None else _default_meshwell_repo_path()
    )
    gsim_path = Path(gsim_repo) if gsim_repo is not None else _default_gsim_repo_path()
    current_handoff_fixture_gap = (
        "covered by the current gsim meshwell-generated MSH handoff fixture"
    )
    gate_rows = [
        _source_contract_row(
            contract_item="meshwell cad_gmsh interface/exterior naming docstring",
            owner_repo="meshwell",
            repo_path=meshwell_path,
            relative_path="meshwell/cad_gmsh.py",
            required_signals=("A___B", "A___None", "mesh_order"),
            current_signal=(
                "meshwell cad_gmsh documents derived interface and exterior "
                "physical groups while preserving mesh_order ownership"
            ),
            remaining_gap=current_handoff_fixture_gap,
        ),
        _source_contract_row(
            contract_item="meshwell cad_gmsh delimiter defaults",
            owner_repo="meshwell",
            repo_path=meshwell_path,
            relative_path="meshwell/cad_gmsh.py",
            required_signals=(
                'interface_delimiter: str = "___"',
                'boundary_delimiter: str = "None"',
            ),
            current_signal="cad_gmsh defaults match meshwell-style interface and exterior labels",
            remaining_gap=current_handoff_fixture_gap,
        ),
        _source_contract_row(
            contract_item="meshwell mesh delimiter defaults",
            owner_repo="meshwell",
            repo_path=meshwell_path,
            relative_path="meshwell/mesh.py",
            required_signals=(
                'interface_delimiter: str = "___"',
                'boundary_delimiter: str = "None"',
            ),
            current_signal="mesh() and in-place model meshing use the same delimiter defaults",
            remaining_gap=current_handoff_fixture_gap,
        ),
        _source_contract_row(
            contract_item="meshwell OCC XAO writer physical-group serializer",
            owner_repo="meshwell",
            repo_path=meshwell_path,
            relative_path="meshwell/occ_xao_writer.py",
            required_signals=(
                "entities, inter-entity interfaces, exterior",
                "A___B",
                "B___None",
                "keep=False",
                'interface_delimiter: str = "___"',
                'boundary_delimiter: str = "None"',
            ),
            current_signal=(
                "meshwell's XAO writer serializes entity, interface, and "
                "exterior physical groups with the same meshwell-style names"
            ),
            remaining_gap=current_handoff_fixture_gap,
        ),
        _source_contract_row(
            contract_item="meshwell multiple physical-name equivalence tests",
            owner_repo="meshwell",
            repo_path=meshwell_path,
            relative_path="tests/test_multiple_physicals.py",
            required_signals=(
                "domain___center",
                "big_prism___None",
                "center___small_prism",
            ),
            current_signal=(
                "meshwell tests show tuple physical names produce equivalent "
                "volume/interface/exterior physical groups"
            ),
            remaining_gap=current_handoff_fixture_gap,
        ),
        _source_contract_row(
            contract_item="meshwell interface sharing and exterior refinement tests",
            owner_repo="meshwell",
            repo_path=meshwell_path,
            relative_path="tests/test_resolution.py",
            required_signals=("outer___None", "outer___A", "outer___B"),
            current_signal="meshwell resolution tests exercise interface and exterior group names",
            remaining_gap=current_handoff_fixture_gap,
        ),
        _source_contract_row(
            contract_item="meshwell CAD backend physical-group equivalence tests",
            owner_repo="meshwell",
            repo_path=meshwell_path,
            relative_path="tests/test_backend_equivalence.py",
            required_signals=(
                "cad_occ",
                "cad_gmsh",
                "A___helper",
                "test_backends_mesh_adjacent_3d_equivalently",
                "test_backends_mesh_keep_false_equivalently",
            ),
            current_signal=(
                "meshwell compares cad_occ/XAO and cad_gmsh physical group "
                "names, masses, duplicate entities, and keep=False behavior"
            ),
            remaining_gap=current_handoff_fixture_gap,
            evidence_status="covered_meshwell_backend_equivalence",
        ),
        _source_contract_row(
            contract_item="meshwell loaded CAD state backend equivalence tests",
            owner_repo="meshwell",
            repo_path=meshwell_path,
            relative_path="tests/test_backend_loaded_equivalence.py",
            required_signals=(
                "physical group names",
                "InterfaceTag",
                "keep=False",
                "multi_physical_names",
                "test_loaded_state_matches",
            ),
            current_signal=(
                "meshwell compares pre-mesh loaded CAD state across backends "
                "for topology-heavy scenes, InterfaceTag, keep=False, and "
                "multiple physical names"
            ),
            remaining_gap=current_handoff_fixture_gap,
            evidence_status="covered_meshwell_backend_equivalence",
        ),
        _source_contract_row(
            contract_item="meshwell mesh-level backend cross-compare tests",
            owner_repo="meshwell",
            repo_path=meshwell_path,
            relative_path="tests/test_backend_cross_compare.py",
            required_signals=(
                "physical groups and per-group geometric mass",
                "InterfaceTag",
                "A___None",
                "test_three_abutting_prisms_match",
                "test_keep_false_helper_match",
            ),
            current_signal=(
                "meshwell compares meshed outputs across backends using "
                "physical group names and per-group mass invariants"
            ),
            remaining_gap=current_handoff_fixture_gap,
            evidence_status="covered_meshwell_backend_equivalence",
        ),
        _source_contract_row(
            contract_item="gsim manifest parser supports meshwell-style names",
            owner_repo="gsim",
            repo_path=gsim_path,
            relative_path="src/gsim/palace/mesh/manifest.py",
            required_signals=(
                '_INTERFACE_DELIMITERS = ("___", "__")',
                '_EXTERIOR_SIDE_NAMES = {"none", "boundary"}',
            ),
            current_signal=(
                "gsim parses meshwell-style interface/exterior labels while "
                "retaining legacy double-underscore compatibility"
            ),
            remaining_gap=(
                "replace legacy compatibility with a single upstream contract only when safe"
            ),
            evidence_status="covered_gsim_consumer_parser",
        ),
        _source_contract_row(
            contract_item="gsim manifest tests cover interface/exterior parsing",
            owner_repo="gsim",
            repo_path=gsim_path,
            relative_path="tests/palace/test_mesh_manifest.py",
            required_signals=(
                "metal___substrate",
                "metal___None",
                "legacy__substrate",
            ),
            current_signal=(
                "gsim tests pin meshwell-style interface/exterior parsing and "
                "legacy artifact parsing"
            ),
            remaining_gap=current_handoff_fixture_gap,
            evidence_status="covered_gsim_consumer_parser",
        ),
        _source_contract_row(
            contract_item="gsim postprocessing index-map lookup helpers",
            owner_repo="gsim",
            repo_path=gsim_path,
            relative_path="src/gsim/palace/mesh/postprocessing.py",
            required_signals=(
                "class PostprocessingIndexMap",
                "physical_name_for_index",
                "entries_for_physical_name",
                "entries_for_attribute",
            ),
            current_signal=(
                "gsim owns section/index-to-physical-name and attribute-to-entry lookup semantics"
            ),
            remaining_gap=current_handoff_fixture_gap,
            evidence_status="covered_gsim_consumer_parser",
        ),
        _source_contract_row(
            contract_item="gsim public postprocessing index-map result loader",
            owner_repo="gsim",
            repo_path=gsim_path,
            relative_path="src/gsim/palace/results.py",
            required_signals=(
                "def load_postprocessing_index_map",
                "palace_index_map.json",
                "PostprocessingIndexMap",
                "_optional_str_pair",
            ),
            current_signal=(
                "gsim exposes a notebook-facing loader for generated "
                "palace_index_map.json artifacts"
            ),
            remaining_gap=current_handoff_fixture_gap,
            evidence_status="covered_gsim_consumer_parser",
        ),
        _source_contract_row(
            contract_item="gsim generated mesh integration tests preserve identities",
            owner_repo="gsim",
            repo_path=gsim_path,
            relative_path="tests/palace/test_mesh_integration.py",
            required_signals=(
                "test_generated_interface_names_use_meshwell_delimiter",
                "test_manifest_preserves_generated_interface_identities",
                "___None",
                "interface_of",
            ),
            current_signal=(
                "gsim integration tests verify generated meshwell-style "
                "interface names and manifest interface identities"
            ),
            remaining_gap=current_handoff_fixture_gap,
            evidence_status="covered_gsim_consumer_parser",
        ),
        _source_contract_row(
            contract_item="formal meshwell physical-name/interface-tag contract text",
            owner_repo="meshwell",
            repo_path=meshwell_path,
            relative_path="docs/physical_name_contract.md",
            required_signals=(
                "GMSH physical groups",
                "The contract is solver-agnostic.",
                "<left><interface_delimiter><right>",
                "`interface_delimiter` is `___`",
                "<physical_name><interface_delimiter><boundary_delimiter>",
                "`boundary_delimiter` is `None`",
                "`mesh_bool=False`",
                "`keep=False`",
                "cad_occ(...)",
                "cad_gmsh(...)",
                "physical group tags only as artifact-local numeric attributes",
            ),
            current_signal=(
                "meshwell now documents the solver-agnostic physical-name "
                "contract for GMSH physical groups, interface/exterior "
                "grammar, helper behavior, CAD route equivalence, and "
                "downstream numeric tag handling"
            ),
            remaining_gap=current_handoff_fixture_gap,
        ),
        _source_contract_row(
            contract_item="gsim meshwell-generated MSH handoff fixture",
            owner_repo="gsim",
            repo_path=gsim_path,
            relative_path=(
                "tests/palace/test_meshwell_handoff_contract/physical_name_contract.msh"
            ),
            required_signals=(
                "$PhysicalNames",
                "A___B",
                "B___helper",
                "A___None",
                "B___None",
            ),
            current_signal=(
                "gsim carries a committed tiny MSH fixture generated from "
                "meshwell cad_gmsh -> mesh output; it includes kept entities, "
                "interfaces, exteriors, and a keep=False helper interface"
            ),
            remaining_gap=(
                "none for the current handoff fixture; regenerate from meshwell "
                "if the physical-name contract changes"
            ),
            evidence_status="covered_cross_repo_consumer_fixture",
        ),
        _source_contract_row(
            contract_item="meshwell-to-gsim cross-repo consumer fixture/gate",
            owner_repo="gsim",
            repo_path=gsim_path,
            relative_path="tests/palace/test_meshwell_handoff_contract.py",
            required_signals=(
                "meshwell-generated MSH fixture",
                "MSH_FIXTURE",
                "gmsh.open",
                "build_mesh_manifest",
                "build_postprocessing_config_from_manifest",
                "load_postprocessing_index_map",
                "A___B",
                "B___helper",
                "A___None",
            ),
            current_signal=(
                "gsim consumes the meshwell-generated MSH fixture, converts "
                "physical groups into manifest categories, builds interface/"
                "exterior relations, writes a Palace index map, and reloads "
                "that map through the public result loader"
            ),
            remaining_gap="none for the current meshwell-to-gsim consumer gate",
            evidence_status="covered_cross_repo_consumer_fixture",
        ),
    ]
    status_counts = _evidence_status_counts(gate_rows)
    missing_source_count = status_counts.get("missing_source_signal", 0)
    covered_statuses = {
        "covered_cross_repo_consumer_fixture",
        "covered_source",
        "covered_meshwell_backend_equivalence",
        "covered_gsim_consumer_parser",
    }
    pending_rows = [
        row for row in gate_rows if str(row["evidence_status"]) == "pending_cross_repo_contract"
    ]
    if missing_source_count:
        contract_status = "source_alignment_incomplete"
    elif pending_rows:
        contract_status = "formal_contract_aligned_pending_cross_repo_fixture"
    else:
        contract_status = "formal_contract_and_cross_repo_gate_aligned"

    evidence_path = output_dir / MESHWELL_HANDOFF_CONTRACT_GATE_FILENAME
    evidence = {
        "schema_version": 1,
        "workflow": "public-meshwell-handoff-contract-gate",
        "repo": "orpen-sc-pdk",
        "meshwell_repo": meshwell_path.as_posix(),
        "gsim_repo": gsim_path.as_posix(),
        "contract_status": contract_status,
        "evidence_status_counts": status_counts,
        "covered_source_count": status_counts.get("covered_source", 0),
        "covered_meshwell_backend_equivalence_count": status_counts.get(
            "covered_meshwell_backend_equivalence",
            0,
        ),
        "covered_gsim_consumer_parser_count": status_counts.get(
            "covered_gsim_consumer_parser",
            0,
        ),
        "covered_cross_repo_consumer_fixture_count": status_counts.get(
            "covered_cross_repo_consumer_fixture",
            0,
        ),
        "covered_count": sum(status_counts.get(status, 0) for status in covered_statuses),
        "pending_count": len(pending_rows),
        "blocking_gaps": [str(row["contract_item"]) for row in pending_rows],
        "owner_boundaries": {
            "meshwell": (
                "solver-agnostic physical names, interface/exterior tag grammar, "
                "XAO/CAD export, and backend equivalence tests"
            ),
            "gsim": (
                "Palace mesh manifest parsing, postprocessing index maps, "
                "config/report lookup, and legacy artifact compatibility"
            ),
            "orpen-sc-pdk": "publication-safe consumer evidence and notebook display",
        },
        "gate_rows": gate_rows,
    }
    evidence["output_dir"] = (
        _relative_path(output_dir, relative_root)
        if relative_root is not None
        else output_dir.as_posix()
    )
    evidence["evidence_path"] = (
        _relative_path(evidence_path, relative_root)
        if relative_root is not None
        else evidence_path.as_posix()
    )
    evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    return evidence


def public_meshwell_handoff_contract_gate_table(
    output_dir: str | Path = DEFAULT_OUTPUT_DIR / "meshwell-handoff-contract-gate",
) -> Any:
    """Return meshwell-to-gsim physical-name handoff contract gate rows."""

    import pandas as pd

    evidence = build_public_meshwell_handoff_contract_gate_evidence(output_dir)
    columns = [
        "contract_item",
        "owner_repo",
        "relative_path",
        "evidence_status",
        "current_signal",
        "remaining_gap",
    ]
    return pd.DataFrame(evidence["gate_rows"]).loc[:, columns]


def load_public_interface_preset_review_queue() -> dict[str, Any]:
    """Load the source-backed dielectric-interface preset review queue."""

    return json.loads(PUBLIC_INTERFACE_PRESET_REVIEW_QUEUE.read_text())


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _relative_result_paths(payload: dict[str, Any], output_root: Path) -> dict[str, Any]:
    for key, value in list(payload.items()):
        if key.endswith("_path") and isinstance(value, str):
            payload[key] = _relative_path(Path(value), output_root)
    return payload


def _relative_run_summary(summary: dict[str, Any], output_root: Path) -> dict[str, Any]:
    for group_name in ("artifacts", "results"):
        group = summary.get(group_name, {})
        if not isinstance(group, dict):
            continue
        for row in group.values():
            if not isinstance(row, dict) or row.get("path") is None:
                continue
            row["path"] = _relative_path(Path(row["path"]), output_root)
    for group_name in ("handoff", "runtime", "resource"):
        group = summary.get(group_name, {})
        if not isinstance(group, dict):
            continue
        if group.get("path") is not None:
            group["path"] = _relative_path(Path(group["path"]), output_root)
        for ref_name in ("script", "archive"):
            ref = group.get(ref_name)
            if isinstance(ref, dict) and ref.get("path") is not None:
                ref["path"] = _relative_path(Path(ref["path"]), output_root)
        if group_name == "resource":
            _relative_resource_refs(group, output_root)
    return summary


def _relative_resource_refs(group: dict[str, Any], output_root: Path) -> None:
    for collection_name in ("sources", "tables"):
        collection = group.get(collection_name)
        if not isinstance(collection, dict):
            continue
        for key, value in list(collection.items()):
            if isinstance(value, dict) and value.get("path") is not None:
                value["path"] = _relative_path(Path(value["path"]), output_root)
            elif isinstance(value, str):
                collection[key] = _relative_path(Path(value), output_root)


def _relative_sweep_summary(
    summary: dict[str, Any],
    output_root: Path,
) -> dict[str, Any]:
    source_path = summary.get("source_path")
    if source_path is not None:
        summary["source_path"] = _relative_path(Path(source_path), output_root)
    handoff = summary.get("handoff")
    if isinstance(handoff, dict):
        if handoff.get("path") is not None:
            handoff["path"] = _relative_path(Path(handoff["path"]), output_root)
        for ref_name in ("script", "archive"):
            ref = handoff.get(ref_name)
            if isinstance(ref, dict) and ref.get("path") is not None:
                ref["path"] = _relative_path(Path(ref["path"]), output_root)
    for point in summary.get("points", []):
        if not isinstance(point, dict):
            continue
        source = point.get("source")
        if isinstance(source, dict):
            point["source"] = {
                name: _relative_path(Path(path), output_root) for name, path in source.items()
            }
        elif source is not None:
            point["source"] = _relative_path(Path(source), output_root)
        run_summary = point.get("run_summary")
        if isinstance(run_summary, dict):
            point["run_summary"] = _relative_run_summary(run_summary, output_root)
    return summary


def _source_summary(rows: Any) -> list[dict[str, Any]]:
    if rows is None or getattr(rows, "empty", True):
        return []
    fields = ("name", "required", "present", "loaded", "message")
    summary = []
    for row in rows.loc[:, [field for field in fields if field in rows.columns]].to_dict("records"):
        summary.append(
            {
                key: bool(value) if key in {"required", "present", "loaded"} else value
                for key, value in row.items()
            }
        )
    return summary


def _json_safe(value: Any) -> Any:
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if hasattr(value, "item"):
        return _json_safe(value.item())
    return value


def _frame_records(rows: Any, columns: Sequence[str]) -> list[dict[str, Any]]:
    if rows is None or getattr(rows, "empty", True):
        return []
    selected_columns = [column for column in columns if column in rows.columns]
    frame = rows.loc[:, selected_columns]
    return [
        {key: _json_safe(value) for key, value in row.items()} for row in frame.to_dict("records")
    ]


def _config_generation_evidence(source: Path) -> dict[str, Any]:
    from gsim.palace import load_domain_material_summary

    config = json.loads((source / "config.json").read_text())
    material_resolution_path = source / "palace_material_resolution.json"
    material_resolution = (
        json.loads(material_resolution_path.read_text())
        if material_resolution_path.exists()
        else {}
    )
    boundaries = config.get("Boundaries", {})
    postprocessing = boundaries.get("Postprocessing", {})
    surface_currents = boundaries.get("SurfaceCurrent", ())
    domains = config.get("Domains", {})
    solver = config.get("Solver", {})
    domain_materials = load_domain_material_summary(source)
    problem_block = next(
        (
            name
            for name in (
                "Driven",
                "Eigenmode",
                "Electrostatic",
                "Magnetostatic",
                "Transient",
            )
            if name in solver
        ),
        None,
    )
    return {
        "problem_type": config.get("Problem", {}).get("Type"),
        "solver_device": solver.get("Device"),
        "solver_has_linear": bool(solver.get("Linear")),
        "solver_problem_block": problem_block,
        "domain_material_count": len(domains.get("Materials", ())),
        "domain_postprocessing_energy_count": len(
            domains.get("Postprocessing", {}).get("Energy", ())
        ),
        "lumped_port_count": len(boundaries.get("LumpedPort", ())),
        "terminal_count": len(boundaries.get("Terminal", ())),
        "wave_port_count": len(boundaries.get("WavePort", ())),
        "surface_current_count": len(surface_currents),
        "surface_current_element_count": sum(
            len(entry.get("Elements", ())) for entry in surface_currents if isinstance(entry, dict)
        ),
        "surface_current_directions": [
            _json_safe(entry.get("Direction"))
            for entry in surface_currents
            if isinstance(entry, dict) and "Direction" in entry
        ],
        "surface_current_coordinate_systems": sorted(
            {
                str(entry["CoordinateSystem"])
                for entry in surface_currents
                if isinstance(entry, dict) and "CoordinateSystem" in entry
            }
            | {
                str(element["CoordinateSystem"])
                for entry in surface_currents
                if isinstance(entry, dict)
                for element in entry.get("Elements", ())
                if isinstance(element, dict) and "CoordinateSystem" in element
            }
        ),
        "pmc_count": int(bool(boundaries.get("PMC"))),
        "surface_flux_count": len(postprocessing.get("SurfaceFlux", ())),
        "dielectric_postprocessing_count": len(postprocessing.get("Dielectric", ())),
        "boundary_sections": sorted(boundaries.keys()),
        "material_resolution": {
            "schema_version": material_resolution.get("schema_version"),
            "material_count": len(material_resolution.get("materials", ())),
            "interface_count": len(material_resolution.get("interfaces", ())),
        },
        "domain_materials": _frame_records(
            domain_materials,
            (
                "domain_index",
                "physical_name",
                "stack_material_name",
                "matched_material_name",
                "material_model_source",
                "material_within_validity",
                "material_frequency_ghz",
                "permittivity",
                "loss_tangent",
                "conductivity",
                "permeability",
            ),
        ),
    }


def _index_map_lookup_evidence(source: Path) -> dict[str, Any]:
    from gsim.palace import load_postprocessing_index_map

    index_map = load_postprocessing_index_map(source)
    lookup_rows: list[dict[str, Any]] = []
    for entry in sorted(
        index_map.entries,
        key=lambda row: (row.section, row.index, row.entry_name),
    ):
        physical_name = index_map.physical_name_for_index(entry.section, entry.index)
        reverse_indices = (
            index_map.indices_for_physical_name(
                physical_name,
                section=entry.section,
            )
            if physical_name is not None
            else ()
        )
        attribute = entry.attributes[0] if entry.attributes else None
        attribute_entry_names = (
            sorted(
                matched.entry_name
                for matched in index_map.entries_for_attribute(
                    attribute,
                    section=entry.section,
                )
            )
            if attribute is not None
            else []
        )
        row = {
            "section": entry.section,
            "index": entry.index,
            "entry_name": entry.entry_name,
            "role": entry.role,
            "physical_name": physical_name,
            "reverse_indices_for_physical_name": list(reverse_indices),
            "attribute": attribute,
            "entry_names_for_attribute": attribute_entry_names,
        }
        if entry.metadata:
            row["metadata"] = dict(entry.metadata)
        if entry.extra:
            row["extra"] = dict(entry.extra)
            if entry.extra.get("terminal_name") is not None:
                row["terminal_name"] = entry.extra["terminal_name"]
            if entry.extra.get("current_source_name") is not None:
                row["current_source_name"] = entry.extra["current_source_name"]
        lookup_rows.append(row)
    return {
        "schema_version": index_map.schema_version,
        "row_count": len(lookup_rows),
        "lookups": lookup_rows,
    }


def _count_values(values: Sequence[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value)
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _manifest_identity_evidence(source: Path) -> dict[str, Any]:
    manifest = json.loads((source / "mesh_manifest.json").read_text())
    entries = list(manifest.get("entries", ()))
    role_names = [entry.get("role") for entry in entries]
    dimension_names = [
        entry.get("dimension") for entry in entries if entry.get("dimension") is not None
    ]
    interface_entries = [entry for entry in entries if entry.get("interface_of") is not None]
    exterior_entries = [entry for entry in entries if entry.get("exterior_of") is not None]
    metadata_keys_by_role: dict[str, list[str]] = {}
    physical_names_by_role: dict[str, list[str]] = {}
    for entry in entries:
        role = str(entry.get("role"))
        metadata = entry.get("metadata")
        if isinstance(metadata, Mapping):
            keys = set(metadata_keys_by_role.get(role, ()))
            keys.update(str(key) for key in metadata)
            metadata_keys_by_role[role] = sorted(keys)
        names = physical_names_by_role.setdefault(role, [])
        names.extend(str(name) for name in entry.get("physical_names", ()) if name)

    entries_without_physical_names = [
        str(entry.get("name")) for entry in entries if not entry.get("physical_names")
    ]
    entries_without_attributes = [
        str(entry.get("name")) for entry in entries if not entry.get("attributes")
    ]
    entries_without_entity_tags = [
        str(entry.get("name")) for entry in entries if not entry.get("entity_tags")
    ]
    return {
        "schema_version": manifest.get("schema_version"),
        "entry_count": len(entries),
        "roles": _count_values(role_names),
        "dimensions": _count_values(dimension_names),
        "physical_name_count": sum(len(entry.get("physical_names", ())) for entry in entries),
        "interface_entry_count": len(interface_entries),
        "interface_physical_names": [
            str(name) for entry in interface_entries for name in entry.get("physical_names", ())
        ],
        "exterior_entry_count": len(exterior_entries),
        "exterior_physical_names": [
            str(name) for entry in exterior_entries for name in entry.get("physical_names", ())
        ],
        "entries_without_physical_names": entries_without_physical_names,
        "entries_without_attributes": entries_without_attributes,
        "entries_without_entity_tags": entries_without_entity_tags,
        "metadata_keys_by_role": dict(sorted(metadata_keys_by_role.items())),
        "physical_names_by_role": {
            role: sorted(dict.fromkeys(names))
            for role, names in sorted(physical_names_by_role.items())
        },
    }


def _public_core_problem_specs() -> tuple[dict[str, Any], ...]:
    return (
        {
            "problem_key": "driven_cpw",
            "fixture_name": "cpw_straight",
            "problem_type": "Driven",
            "build_sim": _public_driven_cpw_sim,
            "build_postprocessing": _driven_postprocessing,
            "report_summary": _driven_report_summary,
            "solver_enabled": True,
            "prepare_local_solver": None,
        },
        {
            "problem_key": "eigenmode_resonator",
            "fixture_name": "resonator",
            "problem_type": "Eigenmode",
            "build_sim": _public_eigenmode_resonator_sim,
            "build_postprocessing": _eigenmode_postprocessing,
            "report_summary": _eigenmode_report_summary,
            "solver_enabled": True,
            "prepare_local_solver": _apply_public_eigenmode_local_smoke_profile,
        },
        {
            "problem_key": "electrostatic_same_layer_capacitor",
            "fixture_name": "martinis2022_differential_ribbon_capacitor",
            "problem_type": "Electrostatic",
            "build_sim": _public_same_layer_capacitor_electrostatic_sim,
            "build_postprocessing": _electrostatic_postprocessing,
            "report_summary": _electrostatic_report_summary,
            "solver_enabled": True,
            "prepare_local_solver": None,
        },
    )


def _public_problem_specs() -> tuple[dict[str, Any], ...]:
    return (
        *_public_core_problem_specs(),
        {
            "problem_key": "magnetostatic_cpw",
            "fixture_name": "cpw_straight",
            "problem_type": "Magnetostatic",
            "build_sim": _public_magnetostatic_cpw_sim,
            "build_postprocessing": _magnetostatic_postprocessing,
            "report_summary": _magnetostatic_report_summary,
            "solver_enabled": False,
            "prepare_local_solver": None,
        },
    )


def _solver_env(environ: Mapping[str, str]) -> tuple[dict[str, Any], dict[str, Any]]:
    if environ.get("ORPEN_RUN_LOCAL_PALACE_SMOKE") != "1":
        return {}, {
            "enabled": False,
            "skip_reason": "set ORPEN_RUN_LOCAL_PALACE_SMOKE=1 to run local Palace smokes",
        }

    palace_sif = environ.get("PALACE_SIF")
    palace_executable = environ.get("PALACE_EXECUTABLE")
    if not palace_sif and not palace_executable:
        return {}, {
            "enabled": False,
            "skip_reason": "set PALACE_SIF or PALACE_EXECUTABLE for local Palace smokes",
        }

    executable_mode = environ.get("PALACE_EXECUTABLE_MODE", "wrapper")
    if executable_mode not in {"wrapper", "binary"}:
        msg = "PALACE_EXECUTABLE_MODE must be 'wrapper' or 'binary'"
        raise ValueError(msg)

    run_kwargs: dict[str, Any] = {
        "use_apptainer": palace_sif is not None,
        "num_processes": int(environ.get("PALACE_NP", "1")),
        "num_threads": int(environ.get("PALACE_NT", "1")),
        "verbose": False,
    }
    if palace_sif is not None:
        run_kwargs["palace_sif_path"] = palace_sif
        launcher = {"kind": "apptainer", "palace_sif_configured": True}
    else:
        run_kwargs["palace_executable"] = palace_executable
        run_kwargs["executable_mode"] = executable_mode
        run_kwargs["serial"] = environ.get("PALACE_SERIAL") == "1"
        launcher = {
            "kind": "executable",
            "palace_executable_configured": True,
            "executable_mode": executable_mode,
            "serial": run_kwargs["serial"],
        }

    return run_kwargs, {
        "enabled": True,
        "skip_reason": None,
        "num_processes": run_kwargs["num_processes"],
        "num_threads": run_kwargs["num_threads"],
        "launcher": launcher,
    }


def _public_slurm_resource_overrides(
    *,
    num_processes: int,
    num_threads: int,
) -> dict[str, int]:
    overrides: dict[str, int] = {}
    if num_processes != 1:
        overrides["ntasks_per_node"] = num_processes
    if num_threads != 1:
        overrides["cpus_per_task"] = num_threads
    return overrides


def _public_driven_cpw_sim(output_dir: Path):
    from gsim.palace import DrivenSim

    orpen_sc_pdk.activate()
    component = cpw_straight(length=300, signal_width=10, gap=6, ground_width=40)

    sim = DrivenSim()
    sim.set_output_dir(output_dir)
    sim.set_geometry(component)
    sim.set_stack(
        include_substrate=True,
        substrate_thickness=20,
        add_oxide_dielectric=False,
        add_passivation_dielectric=False,
    )
    sim.set_airbox(margin_x=40, margin_y=40, z_above=50, z_below=10)
    sim.add_cpw_port("o1", layer="D0_TOP_M1", s_width=10, gap_width=6, length=10)
    sim.add_cpw_port(
        "o2",
        layer="D0_TOP_M1",
        s_width=10,
        gap_width=6,
        length=10,
        excited=False,
    )
    sim.set_driven(fmin=4e9, fmax=8e9, num_points=3, excitation_port="o1")
    sim.mesh(
        preset="coarse",
        refined_mesh_size=20,
        max_mesh_size=200,
        margin_x=40,
        margin_y=40,
        planar_conductors=True,
        auto_size=False,
    )
    return sim, sim._last_mesh_result


def _driven_postprocessing(mesh_result: Any) -> dict[str, Any]:
    from gsim.palace.mesh import SurfaceFluxSpec, build_postprocessing_config_from_manifest

    return build_postprocessing_config_from_manifest(
        mesh_result.manifest,
        surface_flux=(
            SurfaceFluxSpec(
                role="port_surface",
                flux_type="Power",
                two_sided=None,
            ),
        ),
    )


def _driven_report_summary(output_dir: Path) -> dict[str, Any]:
    from gsim.palace import load_driven_report

    report = load_driven_report(output_dir)
    return {
        "status": "loaded",
        "port_names": list(report.sparams.port_names),
        "frequency_points": int(len(report.sparams.freq)),
        "s_parameter_count": int(len(report.sparams.keys())),
        "port_epr_rows": int(len(report.port_epr)),
        "index_map_rows": int(len(report.index_map)),
        "sources": _source_summary(report.sources),
    }


def _public_eigenmode_resonator_sim(output_dir: Path):
    from gsim.palace import EigenmodeSim

    orpen_sc_pdk.activate()
    component = resonator(
        length=1200,
        meanders=2,
        coupling_length=120,
        hanger_straight_length=80,
        cpw_radius=30,
        bend_npoints=8,
    )

    sim = EigenmodeSim()
    sim.set_output_dir(output_dir)
    sim.set_geometry(component)
    sim.set_stack(
        include_substrate=True,
        substrate_thickness=20,
        add_oxide_dielectric=False,
        add_passivation_dielectric=False,
    )
    sim.set_airbox(margin_x=50, margin_y=50, z_above=50, z_below=10)
    sim.set_eigenmode(num_modes=2, target=6e9)
    sim.mesh(
        preset="coarse",
        refined_mesh_size=20,
        max_mesh_size=200,
        margin_x=50,
        margin_y=50,
        planar_conductors=True,
        auto_size=False,
    )
    return sim, sim._last_mesh_result


def _eigenmode_postprocessing(mesh_result: Any) -> dict[str, Any]:
    from gsim.palace.mesh import SurfaceFluxSpec, build_postprocessing_config_from_manifest

    return build_postprocessing_config_from_manifest(
        mesh_result.manifest,
        surface_flux=(
            SurfaceFluxSpec(
                role="boundary_surface",
                entry_names=("absorbing",),
                flux_type="Power",
                two_sided=None,
            ),
        ),
    )


def _eigenmode_report_summary(output_dir: Path) -> dict[str, Any]:
    from gsim.palace import load_eigenmode_report

    report = load_eigenmode_report(output_dir)
    return {
        "status": "loaded",
        "mode_count": int(report.eigenmodes.n_modes),
        "min_frequency_ghz": float(report.eigenmodes.freq_real_ghz.min()),
        "min_q": float(report.eigenmodes.q.min()),
        "domain_energy_rows": int(len(report.domain_energy)),
        "surface_q_rows": int(len(report.surface_q)),
        "index_map_rows": int(len(report.index_map)),
        "sources": _source_summary(report.sources),
    }


def _public_same_layer_capacitor_electrostatic_sim(output_dir: Path):
    from gsim.palace import ElectrostaticSim

    orpen_sc_pdk.activate()
    component = martinis2022_differential_ribbon_capacitor(
        a_um=20,
        b_um=35,
        ell_r_um=160,
    )
    positive_port = component.ports["o_mesh_positive_electrode"]
    negative_port = component.ports["o_mesh_negative_electrode"]
    positive_center = tuple(float(value) for value in positive_port.center)
    negative_center = tuple(float(value) for value in negative_port.center)

    sim = ElectrostaticSim()
    sim.set_output_dir(output_dir)
    sim.set_geometry(component)
    sim.set_stack(
        include_substrate=True,
        substrate_thickness=20,
        add_oxide_dielectric=False,
        add_passivation_dielectric=False,
    )
    sim.set_airbox(margin_x=40, margin_y=40, z_above=50, z_below=10)
    sim.add_terminal("positive", layer="D0_TOP_M1", center=positive_center)
    sim.add_terminal("negative", layer="D0_TOP_M1", center=negative_center)
    sim.set_electrostatic(save_fields=0)
    sim.mesh(
        preset="coarse",
        refined_mesh_size=20,
        max_mesh_size=200,
        margin_x=40,
        margin_y=40,
        planar_conductors=True,
        auto_size=False,
    )
    return sim, sim._last_mesh_result


def _electrostatic_postprocessing(mesh_result: Any) -> dict[str, Any]:
    from gsim.palace.mesh import build_postprocessing_config_from_manifest

    return build_postprocessing_config_from_manifest(mesh_result.manifest)


def _electrostatic_report_summary(output_dir: Path) -> dict[str, Any]:
    from gsim.palace import load_electrostatic_report

    report = load_electrostatic_report(output_dir)
    return {
        "status": "loaded",
        "terminal_names": list(report.capacitance.terminal_names),
        "capacitance_shape": list(report.capacitance.dataframe.shape),
        "has_mutual_capacitance": report.mutual_capacitance is not None,
        "has_inverse_capacitance": report.inverse_capacitance is not None,
        "domain_energy_rows": int(len(report.domain_energy)),
        "surface_q_rows": int(len(report.surface_q)),
        "index_map_rows": int(len(report.index_map)),
        "sources": _source_summary(report.sources),
    }


def _write_public_report_json(path: Path, data: Mapping[str, Any]) -> Path:
    path.write_text(json.dumps(dict(data), indent=2, sort_keys=True) + "\n")
    return path


def _public_report_material_resolution() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "materials": [
            {
                "material_row_index": 1,
                "material_attribute": 10,
                "material_attributes": [10],
                "volume_name": "substrate",
                "stack_material_name": "Si",
                "matched_material_name": "Si",
                "evaluation_frequency_hz": 5.0e9,
                "evaluation_frequency_ghz": 5.0,
                "model_type": "constant",
                "model_source": "orpen-sc-pdk tech.material_properties",
                "within_validity": True,
                "validity_note": None,
                "effective_material": {
                    "permittivity": 11.45,
                    "loss_tangent": 2.0e-6,
                },
                "palace_material": {
                    "Attributes": [10],
                    "Name": "Si",
                    "Permittivity": 11.45,
                    "LossTan": 2.0e-6,
                },
            }
        ],
        "interfaces": [
            {
                "interface_row_index": 1,
                "surface_index": 2,
                "surface_attributes": [20],
                "interface_type": "SA",
                "interface_material_name": "AlOx_native_generic",
                "matched_material_name": "AlOx_native_generic",
                "evaluation_frequency_hz": 5.0e9,
                "evaluation_frequency_ghz": 5.0,
                "model_type": "constant",
                "model_source": "orpen-sc-pdk tech.material_properties",
                "within_validity": True,
                "validity_note": None,
                "effective_material": {
                    "permittivity": 10.0,
                    "loss_tangent": 0.0017,
                },
                "palace_interface": {
                    "Index": 2,
                    "Attributes": [20],
                    "Type": "SA",
                    "Thickness": 0.003,
                    "Permittivity": 10.0,
                    "LossTan": 0.0017,
                },
            }
        ],
    }


def _write_public_driven_report_fixture(output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    port_info_path = _write_public_report_json(
        output_dir / "port_information.json",
        {
            "ports": [
                {"portnumber": 1, "name": "o1", "Z0": 50.0, "type": "cpw"},
                {"portnumber": 2, "name": "o2", "Z0": 50.0, "type": "cpw"},
            ],
            "unit": 1e-6,
            "name": "palace",
        },
    )
    port_s_path = output_dir / "port-S.csv"
    port_s_path.write_text(
        "f (GHz), |S[1][1]| (dB), arg(S[1][1]) (deg.), "
        "|S[2][1]| (dB), arg(S[2][1]) (deg.)\n"
        "4.0, -18.0, -45.0, -3.0, -90.0\n"
        "6.0, -12.0, -50.0, -2.0, -95.0\n"
        "8.0, -16.0, -55.0, -4.0, -100.0\n"
    )
    port_epr_path = output_dir / "port-EPR.csv"
    port_epr_path.write_text("m, p[3], p[4]\n1, 0.60, 0.40\n")
    config_path = _write_public_report_json(
        output_dir / "config.json",
        {
            "Domains": {
                "Materials": [
                    {
                        "Attributes": [10],
                        "Name": "Si",
                        "Permittivity": 11.45,
                        "LossTan": 2.0e-6,
                    }
                ]
            }
        },
    )
    index_map_path = _write_public_report_json(
        output_dir / "palace_index_map.json",
        {
            "schema_version": 1,
            "entries": [
                {
                    "section": "Domains.Postprocessing.Energy",
                    "index": 1,
                    "entry_name": "substrate",
                    "role": "dielectric_volume",
                    "attributes": [10],
                    "physical_names": ["D1_SUBSTRATE"],
                    "dimension": 3,
                },
                {
                    "section": "Boundaries.Postprocessing.SurfaceFlux",
                    "index": 3,
                    "entry_name": "o1_port_surface",
                    "role": "port_surface",
                    "attributes": [31],
                    "physical_names": ["P1_E0"],
                    "dimension": 2,
                    "Type": "Power",
                    "metadata": {"port": "P1", "port_type": "cpw"},
                },
                {
                    "section": "Boundaries.Postprocessing.SurfaceFlux",
                    "index": 4,
                    "entry_name": "o2_port_surface",
                    "role": "port_surface",
                    "attributes": [41],
                    "physical_names": ["P2_E0"],
                    "dimension": 2,
                    "Type": "Power",
                    "metadata": {"port": "P2", "port_type": "cpw"},
                },
            ],
        },
    )
    material_resolution_path = _write_public_report_json(
        output_dir / "palace_material_resolution.json",
        _public_report_material_resolution(),
    )
    return {
        "port-S.csv": port_s_path,
        "port-EPR.csv": port_epr_path,
        "port_information.json": port_info_path,
        "config.json": config_path,
        "palace_index_map.json": index_map_path,
        "palace_material_resolution.json": material_resolution_path,
    }


def _write_public_eigenmode_report_fixture(output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    eig_path = output_dir / "eig.csv"
    eig_path.write_text(
        "m, Re{f} (GHz), Im{f} (GHz), Q, Error (Bkwd.), Error (Abs.)\n"
        "1, 5.0, 0.0, 2.0e6, 0.0, 0.0\n"
    )
    domain_e_path = output_dir / "domain-E.csv"
    domain_e_path.write_text("m, E_elec[1] (J), p_elec[1]\n1, 1.0, 0.25\n")
    surface_q_path = output_dir / "surface-Q.csv"
    surface_q_path.write_text("m, p_surf[2], Q_surf[2]\n1, 0.125, 1.0e6\n")
    config_path = _write_public_report_json(
        output_dir / "config.json",
        {
            "Domains": {
                "Materials": [
                    {
                        "Attributes": [10],
                        "Name": "Si",
                        "Permittivity": 11.45,
                        "LossTan": 2.0e-6,
                    }
                ]
            },
            "Boundaries": {
                "Postprocessing": {
                    "Dielectric": [
                        {
                            "Index": 2,
                            "Attributes": [20],
                            "Type": "SA",
                            "Thickness": 0.003,
                            "Permittivity": 10.0,
                            "LossTan": 0.0017,
                        }
                    ]
                }
            },
        },
    )
    index_map_path = _write_public_report_json(
        output_dir / "palace_index_map.json",
        {
            "schema_version": 1,
            "entries": [
                {
                    "section": "Domains.Postprocessing.Energy",
                    "index": 1,
                    "entry_name": "substrate",
                    "role": "dielectric_volume",
                    "attributes": [10],
                    "physical_names": ["D1_SUBSTRATE"],
                    "dimension": 3,
                },
                {
                    "section": "Boundaries.Postprocessing.Dielectric",
                    "index": 2,
                    "entry_name": "sa_interface",
                    "role": "boundary_surface",
                    "attributes": [20],
                    "physical_names": ["SA:D1_SUBSTRATE___OUTER_VACUUM"],
                    "dimension": 2,
                    "Type": "SA",
                },
            ],
        },
    )
    material_resolution_path = _write_public_report_json(
        output_dir / "palace_material_resolution.json",
        _public_report_material_resolution(),
    )
    return {
        "eig.csv": eig_path,
        "domain-E.csv": domain_e_path,
        "surface-Q.csv": surface_q_path,
        "config.json": config_path,
        "palace_index_map.json": index_map_path,
        "palace_material_resolution.json": material_resolution_path,
    }


def _write_public_electrostatic_report_fixture(output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    terminal_c_path = output_dir / "terminal-C.csv"
    terminal_c_path.write_text(
        "i, C[i][1] (F), C[i][2] (F)\n1.00e+00, 1.0e-15, -2.0e-15\n2.00e+00, -2.0e-15, 4.0e-15\n"
    )
    domain_e_path = output_dir / "domain-E.csv"
    domain_e_path.write_text("i, E_elec[1] (J), p_elec[1]\n1, 1.0, 0.25\n2, 1.0, 0.125\n")
    surface_q_path = output_dir / "surface-Q.csv"
    surface_q_path.write_text("i, p_surf[2], Q_surf[2]\n1, 0.125, 1.0e6\n2, 0.25, 2.0e6\n")
    config_path = _write_public_report_json(
        output_dir / "config.json",
        {
            "Domains": {
                "Materials": [
                    {
                        "Attributes": [10],
                        "Name": "Si",
                        "Permittivity": 11.45,
                        "LossTan": 2.0e-6,
                    }
                ]
            },
            "Boundaries": {
                "Postprocessing": {
                    "Dielectric": [
                        {
                            "Index": 2,
                            "Attributes": [20],
                            "Type": "SA",
                            "Thickness": 0.003,
                            "Permittivity": 10.0,
                            "LossTan": 0.0017,
                        }
                    ]
                }
            },
        },
    )
    index_map_path = _write_public_report_json(
        output_dir / "palace_index_map.json",
        {
            "schema_version": 1,
            "entries": [
                {
                    "section": "Boundaries.Terminal",
                    "index": 1,
                    "entry_name": "positive_electrode",
                    "role": "pec_surface",
                    "attributes": [11],
                    "physical_names": ["D0_TOP_M1@positive"],
                    "dimension": 2,
                    "terminal_name": "positive",
                },
                {
                    "section": "Boundaries.Terminal",
                    "index": 2,
                    "entry_name": "negative_electrode",
                    "role": "pec_surface",
                    "attributes": [12],
                    "physical_names": ["D0_TOP_M1@negative"],
                    "dimension": 2,
                    "terminal_name": "negative",
                },
                {
                    "section": "Domains.Postprocessing.Energy",
                    "index": 1,
                    "entry_name": "substrate",
                    "role": "dielectric_volume",
                    "attributes": [10],
                    "physical_names": ["D1_SUBSTRATE"],
                    "dimension": 3,
                },
                {
                    "section": "Boundaries.Postprocessing.Dielectric",
                    "index": 2,
                    "entry_name": "sa_interface",
                    "role": "boundary_surface",
                    "attributes": [20],
                    "physical_names": ["SA:D1_SUBSTRATE___OUTER_VACUUM"],
                    "dimension": 2,
                    "Type": "SA",
                },
            ],
        },
    )
    material_resolution_path = _write_public_report_json(
        output_dir / "palace_material_resolution.json",
        _public_report_material_resolution(),
    )
    return {
        "terminal-C.csv": terminal_c_path,
        "domain-E.csv": domain_e_path,
        "surface-Q.csv": surface_q_path,
        "config.json": config_path,
        "palace_index_map.json": index_map_path,
        "palace_material_resolution.json": material_resolution_path,
    }


def build_public_driven_cpw_sim(output_dir: str | Path) -> tuple[Any, Any]:
    """Build the public Driven CPW fixture and return the sim plus mesh result."""

    return _public_driven_cpw_sim(Path(output_dir))


def build_public_driven_postprocessing(mesh_result: Any) -> dict[str, Any]:
    """Build Driven postprocessing from the generated mesh manifest."""

    return _driven_postprocessing(mesh_result)


def build_public_eigenmode_resonator_sim(output_dir: str | Path) -> tuple[Any, Any]:
    """Build the public Eigenmode resonator fixture and return the sim plus mesh result."""

    return _public_eigenmode_resonator_sim(Path(output_dir))


def build_public_eigenmode_postprocessing(mesh_result: Any) -> dict[str, Any]:
    """Build Eigenmode postprocessing from the generated mesh manifest."""

    return _eigenmode_postprocessing(mesh_result)


def build_public_eigenmode_interface_postprocessing(mesh_result: Any) -> dict[str, Any]:
    """Build caller-supplied Eigenmode dielectric-interface postprocessing."""

    from gsim.palace.mesh import (
        build_dielectric_interface_specs_from_material_kinds,
        build_postprocessing_config_from_manifest,
    )

    from orpen_sc_pdk.materials import (
        get_gsim_material_kind_alias_map,
        get_gsim_material_kind_map,
        validate_interface_preset_records,
    )

    interface_records = {
        "public_sa_example": {
            "interface_type": "SA",
            "thickness": 0.003,
            "material_name": "AlOx_native_generic",
            "source": "public notebook fixture only",
        }
    }
    dielectric_interfaces = build_dielectric_interface_specs_from_material_kinds(
        mesh_result.manifest,
        material_kind_by_name=get_gsim_material_kind_map(),
        material_name_aliases=get_gsim_material_kind_alias_map(),
        presets=validate_interface_preset_records(interface_records),
        preset_by_interface_type={"SA": "public_sa_example"},
    )
    return build_postprocessing_config_from_manifest(
        mesh_result.manifest,
        dielectric_interfaces=dielectric_interfaces,
    )


def build_public_electrostatic_capacitor_sim(output_dir: str | Path) -> tuple[Any, Any]:
    """Build the public Electrostatic capacitor fixture and return the sim plus mesh result."""

    return _public_same_layer_capacitor_electrostatic_sim(Path(output_dir))


def build_public_electrostatic_postprocessing(mesh_result: Any) -> dict[str, Any]:
    """Build Electrostatic postprocessing from the generated mesh manifest."""

    return _electrostatic_postprocessing(mesh_result)


def load_public_json(path: str | Path) -> dict[str, Any]:
    """Load a JSON artifact produced by a public simulation workflow."""

    return json.loads(Path(path).read_text())


def write_public_json(path: str | Path, data: Mapping[str, Any]) -> Path:
    """Write a small public JSON fixture used by notebook examples."""

    path = Path(path)
    path.write_text(json.dumps(dict(data), indent=2, sort_keys=True) + "\n")
    return path


def public_artifact_status(output_dir: str | Path) -> dict[str, bool]:
    """Report whether the standard public mesh/config artifacts exist."""

    output_dir = Path(output_dir)
    return {
        name: (output_dir / name).exists()
        for name in (
            "palace.msh",
            "config.json",
            "mesh_manifest.json",
            "palace_index_map.json",
        )
    }


def resolve_public_slurm_profile(
    profile_name: str,
    *,
    num_processes: int = 1,
    num_threads: int = 1,
) -> Any:
    """Resolve a docs-safe public Slurm profile through the `gsim` handoff API."""

    from gsim.palace.handoff import (
        load_palace_slurm_profile_catalog,
        resolve_palace_slurm_profile,
    )

    resource_overrides = _public_slurm_resource_overrides(
        num_processes=num_processes,
        num_threads=num_threads,
    )
    profiles = load_palace_slurm_profile_catalog(PUBLIC_SLURM_PROFILE_CATALOG)
    return resolve_palace_slurm_profile(
        profiles,
        profile_name,
        resource_overrides=resource_overrides,
    )


def public_solver_config_hints() -> dict[str, Any]:
    """Return public dry-run solver hints for Palace config generation."""

    return resolve_public_slurm_profile("public-slurm-dry-run").to_palace_config_hints()


def preview_public_slurm_script(script_path: str | Path) -> list[str]:
    """Return the scheduler-relevant lines from a generated public Slurm script."""

    return [
        line
        for line in Path(script_path).read_text().splitlines()
        if line.startswith("#SBATCH") or line.startswith("srun")
    ]


def public_simulation_helper_node_inventory_table() -> Any:
    """Return the public helper-node inventory as a notebook table."""

    import pandas as pd

    columns = [
        "node",
        "private_capability",
        "private_anchor",
        "why_helper_exists",
        "gdsfactory_home",
        "public_api_or_artifact",
        "public_status",
        "promotion_gate",
        "missing_evidence",
        "next_issue",
    ]
    return pd.DataFrame(load_public_simulation_helper_node_inventory()).loc[:, columns]


def public_problem_notebook_crosscheck_table() -> Any:
    """Return the representative notebook cross-check as a notebook table."""

    import pandas as pd

    columns = [
        "problem_type",
        "private_representative_notebook",
        "private_capability_anchor",
        "public_notebook",
        "public_helper_node",
        "gdsfactory_home",
        "owner_decision",
        "gsim_api_or_artifact",
        "notebook_support_wrapper",
        "coverage_status",
        "missing_evidence",
        "next_issue",
    ]
    return pd.DataFrame(load_public_problem_notebook_crosscheck()).loc[:, columns]


def public_simulation_goal_audit_table() -> Any:
    """Return the goal-level simulation migration audit as a notebook table."""

    import pandas as pd

    columns = [
        "objective_requirement",
        "current_status",
        "current_evidence",
        "remaining_gap",
        "next_issue",
    ]
    return pd.DataFrame(load_public_simulation_goal_audit()).loc[:, columns]


def public_gsim_boundary_review_crosscheck_table() -> Any:
    """Return the local gsim commit boundary-review matrix as a notebook table."""

    import pandas as pd

    columns = [
        "commit",
        "summary",
        "boundary_group",
        "review_status",
        "ecosystem_home",
        "owner_surface",
        "evidence_anchor",
    ]
    return pd.DataFrame(load_public_gsim_boundary_review_crosscheck()).loc[:, columns]


def public_interface_preset_source_review_table() -> Any:
    """Return source-review rows for public dielectric-interface preset candidates."""

    import pandas as pd

    columns = [
        "source_id",
        "source",
        "doi",
        "candidate_use",
        "review_status",
    ]
    queue = load_public_interface_preset_review_queue()
    return pd.DataFrame(queue["sources"]).loc[:, columns]


def public_interface_preset_candidate_review_table() -> Any:
    """Return candidate rows for public dielectric-interface preset review."""

    import pandas as pd

    columns = [
        "candidate_record",
        "source_id",
        "role",
        "geometry_family",
        "thickness_um",
        "material_or_permittivity",
        "loss_tangent",
        "extracted_fields_status",
        "promotion_status",
        "public_default_status",
        "owner_repo",
        "promotion_gate",
    ]
    queue = load_public_interface_preset_review_queue()
    return pd.DataFrame(queue["candidate_records"]).loc[:, columns]


def _source_review_by_id(queue: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(source["source_id"]): source
        for source in queue.get("sources", ())
        if isinstance(source, Mapping)
    }


def _interface_preset_candidate_gate_rows(
    queue: Mapping[str, Any],
) -> list[dict[str, Any]]:
    sources = _source_review_by_id(queue)
    rows = []
    for candidate in queue.get("candidate_records", ()):
        if not isinstance(candidate, Mapping):
            continue
        role = str(candidate.get("role"))
        is_interface_candidate = role in INTERFACE_PRESET_ROLES
        public_default_status = str(candidate.get("public_default_status"))
        promotion_status = str(candidate.get("promotion_status"))
        source_id = str(candidate.get("source_id"))
        missing_decisions = []
        if is_interface_candidate and not promotion_status.startswith("accepted"):
            missing_decisions.append("accepted_candidate_id")
        if is_interface_candidate:
            missing_decisions.extend(("process_scope", "default_selection_rule"))
        if public_default_status != "public_default":
            missing_decisions.append("public_default_decision")

        if not is_interface_candidate:
            readiness_status = "not_interface_preset"
        elif missing_decisions:
            readiness_status = "awaiting_public_policy"
        else:
            readiness_status = "ready_for_public_default"

        rows.append(
            {
                "candidate_record": candidate.get("candidate_record"),
                "role": role,
                "is_interface_preset_candidate": is_interface_candidate,
                "source_id": source_id,
                "source_review_status": sources.get(source_id, {}).get("review_status"),
                "geometry_family": candidate.get("geometry_family"),
                "has_thickness": candidate.get("thickness_um") is not None,
                "has_material_or_permittivity": bool(candidate.get("material_or_permittivity")),
                "has_loss_tangent": candidate.get("loss_tangent") is not None,
                "extracted_fields_status": candidate.get("extracted_fields_status"),
                "promotion_status": promotion_status,
                "public_default_status": public_default_status,
                "promotion_gate": candidate.get("promotion_gate"),
                "readiness_status": readiness_status,
                "missing_decisions": missing_decisions,
                "owner_repo": candidate.get("owner_repo"),
                "gsim_handoff": candidate.get("gsim_handoff"),
            }
        )
    return rows


def build_public_interface_preset_promotion_gate_evidence(
    output_dir: str | Path = DEFAULT_OUTPUT_DIR / "interface-preset-promotion-gate",
    *,
    relative_to: str | Path | None = None,
) -> dict[str, Any]:
    """Build source-backed interface-preset promotion gate evidence."""

    from orpen_sc_pdk.materials import get_interface_preset_records

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    relative_root = Path(relative_to) if relative_to is not None else None
    queue = load_public_interface_preset_review_queue()
    gate_rows = _interface_preset_candidate_gate_rows(queue)
    public_default_rows = [
        row for row in gate_rows if row["public_default_status"] == "public_default"
    ]
    accepted_interface_rows = [
        row
        for row in gate_rows
        if row["is_interface_preset_candidate"]
        and str(row["promotion_status"]).startswith("accepted")
    ]
    pdk_records = get_interface_preset_records()
    evidence = {
        "schema_version": 1,
        "workflow": "public-interface-preset-promotion-gate",
        "repo": "orpen-sc-pdk",
        "promotion_policy": queue["promotion_policy"],
        "owner_boundaries": {
            "orpen-sc-pdk": (
                "public process/material preset records, source review, "
                "accepted default policy, and validation"
            ),
            "gsim": (
                "DielectricInterfaceSpec assignment, material-kind "
                "classification, Palace config emission, and report joins"
            ),
        },
        "default_policy_status": ("defined" if public_default_rows else "not_defined"),
        "pdk_interface_preset_record_count": len(pdk_records),
        "tech_interface_preset_records_populated": bool(pdk_records),
        "accepted_interface_candidate_ids": [
            str(row["candidate_record"]) for row in accepted_interface_rows
        ],
        "public_default_candidate_ids": [
            str(row["candidate_record"]) for row in public_default_rows
        ],
        "source_count": len(queue.get("sources", ())),
        "candidate_count": len(gate_rows),
        "interface_candidate_count": sum(
            1 for row in gate_rows if row["is_interface_preset_candidate"]
        ),
        "role_counts": _count_values([row["role"] for row in gate_rows]),
        "readiness_counts": _count_values([row["readiness_status"] for row in gate_rows]),
        "required_acceptance_fields": [
            "accepted_candidate_id",
            "process_scope",
            "default_selection_rule",
            "source_id",
            "role",
            "thickness_um",
            "material_or_permittivity",
            "loss_tangent",
            "source_basis",
        ],
        "open_decisions": list(queue.get("open_decisions", ())),
        "candidate_gate_rows": gate_rows,
    }
    evidence_path = output_dir / INTERFACE_PRESET_PROMOTION_GATE_FILENAME
    evidence["output_dir"] = (
        _relative_path(output_dir, relative_root)
        if relative_root is not None
        else output_dir.as_posix()
    )
    evidence["evidence_path"] = (
        _relative_path(evidence_path, relative_root)
        if relative_root is not None
        else evidence_path.as_posix()
    )
    evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    return evidence


def public_interface_preset_promotion_gate_table(
    output_dir: str | Path = DEFAULT_OUTPUT_DIR / "interface-preset-promotion-gate",
) -> Any:
    """Return source-backed interface-preset promotion gate evidence."""

    import pandas as pd

    evidence = build_public_interface_preset_promotion_gate_evidence(output_dir)
    columns = [
        "candidate_record",
        "role",
        "source_review_status",
        "promotion_status",
        "public_default_status",
        "readiness_status",
        "missing_decisions",
        "gsim_handoff",
    ]
    return pd.DataFrame(evidence["candidate_gate_rows"]).loc[:, columns]


def build_public_thin_film_sheet_proxy_interface_evidence(
    output_dir: str | Path = DEFAULT_OUTPUT_DIR / "thin-film-sheet-proxy-interface",
    *,
    relative_to: str | Path | None = None,
) -> dict[str, Any]:
    """Build public evidence for caller-supplied thin-film MA/MS proxy specs."""

    from gsim.common.stack import LayerStack
    from gsim.palace import load_dielectric_interface_summary
    from gsim.palace.mesh import (
        build_dielectric_interface_specs_from_material_kinds,
        build_postprocessing_config_from_manifest,
    )
    from gsim.palace.mesh.config_generator import generate_palace_config
    from gsim.palace.mesh.manifest import build_mesh_manifest

    from orpen_sc_pdk.materials import (
        get_gsim_material_kind_alias_map,
        get_gsim_material_kind_map,
        get_interface_preset_records,
        validate_interface_preset_records,
    )

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    relative_root = Path(relative_to) if relative_to is not None else None
    groups = {
        "volumes": {
            "silicon": {"phys_group": 1},
            "air": {"phys_group": 2},
        },
        "conductor_surfaces": {},
        "pec_surfaces": {},
        "port_surfaces": {},
        "boundary_surfaces": {
            "Al___air": {"phys_group": 71, "tags": [701], "dim": 2},
            "Al___silicon": {"phys_group": 72, "tags": [702], "dim": 2},
        },
    }
    caller_records = {
        "public_ma_sheet_proxy_example": {
            "interface_type": "MA",
            "thickness": 0.003,
            "material_name": "AlOx_native_generic",
            "source": "public thin-film sheet proxy fixture only",
        },
        "public_ms_sheet_proxy_example": {
            "interface_type": "MS",
            "thickness": 0.003,
            "material_name": "AlOx_native_generic",
            "source": "public thin-film sheet proxy fixture only",
        },
    }
    manifest = build_mesh_manifest(groups)
    dielectric_interfaces = build_dielectric_interface_specs_from_material_kinds(
        manifest,
        material_kind_by_name=get_gsim_material_kind_map(),
        material_name_aliases=get_gsim_material_kind_alias_map(),
        presets=validate_interface_preset_records(caller_records),
        preset_by_interface_type={
            "MA": "public_ma_sheet_proxy_example",
            "MS": "public_ms_sheet_proxy_example",
        },
    )
    postprocessing = build_postprocessing_config_from_manifest(
        manifest,
        dielectric_interfaces=dielectric_interfaces,
    )
    config_path = generate_palace_config(
        groups=groups,
        ports=[],
        port_info=[],
        stack=LayerStack(
            materials={
                "silicon": {"permittivity": 11.9},
                "air": {"permittivity": 1.0},
            }
        ),
        output_path=output_dir,
        model_name="palace",
        fmax=5e9,
        absorbing_boundary=False,
        boundary_postprocessing_config=postprocessing.boundaries,
        material_overlay=get_gsim_material_overlay(),
    )
    index_map_path = output_dir / "palace_index_map.json"
    postprocessing.index_map.write_json(index_map_path)

    summary = load_dielectric_interface_summary(
        {
            "config.json": config_path,
            "palace_index_map.json": index_map_path,
        }
    )
    config = json.loads(Path(config_path).read_text())
    return {
        "schema_version": 1,
        "workflow": "public-thin-film-sheet-proxy-interface",
        "public_default_status": "not_public_default",
        "caller_record_source": "public thin-film sheet proxy fixture only",
        "pdk_interface_preset_record_count": len(get_interface_preset_records()),
        "output_dir": (
            _relative_path(output_dir, relative_root)
            if relative_root is not None
            else output_dir.as_posix()
        ),
        "config_path": (
            _relative_path(Path(config_path), relative_root)
            if relative_root is not None
            else Path(config_path).as_posix()
        ),
        "index_map_path": (
            _relative_path(index_map_path, relative_root)
            if relative_root is not None
            else index_map_path.as_posix()
        ),
        "specs": [
            {
                "interface_type": spec.interface_type,
                "entry_names": list(spec.entry_names),
                "preset_name": spec.preset_name,
                "preset_source": spec.preset_source,
                "material_name": spec.material_name,
                "role": spec.role,
            }
            for spec in dielectric_interfaces
        ],
        "config_rows": config["Boundaries"]["Postprocessing"]["Dielectric"],
        "summary_rows": _frame_records(
            summary,
            (
                "surface_index",
                "source_name",
                "interface_type",
                "preset_name",
                "preset_source",
                "interface_material_name",
                "matched_material_name",
                "material_model_source",
                "thickness",
                "permittivity",
                "loss_tangent",
            ),
        ),
    }


def public_thin_film_sheet_proxy_interface_table(
    output_dir: str | Path = DEFAULT_OUTPUT_DIR / "thin-film-sheet-proxy-interface",
) -> Any:
    """Return public thin-film MA/MS proxy evidence as a notebook table."""

    import pandas as pd

    evidence = build_public_thin_film_sheet_proxy_interface_evidence(output_dir)
    columns = [
        "surface_index",
        "source_name",
        "interface_type",
        "preset_name",
        "preset_source",
        "interface_material_name",
        "matched_material_name",
        "material_model_source",
    ]
    return pd.DataFrame(evidence["summary_rows"]).loc[:, columns]


def public_domain_material_table(output_dir: str | Path) -> Any:
    """Load the public domain-material provenance table for a generated config."""

    from gsim.palace import load_domain_material_summary

    frame = load_domain_material_summary(Path(output_dir))
    columns = [
        "domain_index",
        "physical_name",
        "stack_material_name",
        "matched_material_name",
        "material_model_source",
        "material_within_validity",
        "material_frequency_ghz",
        "permittivity",
        "loss_tangent",
        "conductivity",
        "permeability",
    ]
    selected_columns = [column for column in columns if column in frame.columns]
    return frame.loc[:, selected_columns].copy()


def public_index_map_lookup_table(
    output_dir: str | Path,
    *,
    sections: tuple[str, ...] | None = None,
) -> Any:
    """Load section/index lookup rows from the public Palace index map."""

    import pandas as pd
    from gsim.palace import load_postprocessing_index_map

    index_map = load_postprocessing_index_map(Path(output_dir))
    rows: list[dict[str, Any]] = []
    for entry in sorted(
        index_map.entries,
        key=lambda row: (row.section, row.index, row.entry_name),
    ):
        if sections is not None and entry.section not in sections:
            continue
        physical_name = index_map.physical_name_for_index(entry.section, entry.index)
        reverse_indices = (
            index_map.indices_for_physical_name(physical_name, section=entry.section)
            if physical_name is not None
            else ()
        )
        attribute = entry.attributes[0] if entry.attributes else None
        attribute_entry_names = (
            [
                matched.entry_name
                for matched in index_map.entries_for_attribute(
                    attribute,
                    section=entry.section,
                )
            ]
            if attribute is not None
            else []
        )
        rows.append(
            {
                "section": entry.section,
                "index": entry.index,
                "physical_name": physical_name,
                "reverse_indices_for_physical_name": list(reverse_indices),
                "attribute": attribute,
                "entry_names_for_attribute": attribute_entry_names,
                "entry_name": entry.entry_name,
                "role": entry.role,
                "port": entry.metadata.get("port"),
                "terminal_name": entry.extra.get("terminal_name"),
                "current_source_name": entry.extra.get("current_source_name"),
                "current_source_element_index": entry.extra.get("current_source_element_index"),
                "current_source_element_count": entry.extra.get("current_source_element_count"),
                "direction": entry.extra.get("Direction"),
                "coordinate_system": entry.extra.get("CoordinateSystem"),
                "type": entry.extra.get("Type"),
            }
        )
    return pd.DataFrame(rows)


def public_config_generation_summary(output_dir: str | Path) -> dict[str, Any]:
    """Return notebook-sized config/material/index summary fields."""

    output_dir = Path(output_dir)
    config = load_public_json(output_dir / "config.json")
    evidence = _config_generation_evidence(output_dir)
    return {
        "problem_type": evidence["problem_type"],
        "solver_device": evidence["solver_device"],
        "solver_problem_block": evidence["solver_problem_block"],
        "solver_has_linear": evidence["solver_has_linear"],
        "domain_material_count": evidence["domain_material_count"],
        "domain_material_rows": len(evidence["domain_materials"]),
        "domain_postprocessing_energy_count": evidence["domain_postprocessing_energy_count"],
        "surface_flux_count": evidence["surface_flux_count"],
        "dielectric_postprocessing_count": evidence["dielectric_postprocessing_count"],
        "lumped_port_count": evidence["lumped_port_count"],
        "terminal_count": evidence["terminal_count"],
        "boundary_sections": evidence["boundary_sections"],
        "config_problem_type": config["Problem"]["Type"],
    }


def select_public_report_table(
    frame: Any,
    columns: Sequence[str],
    *,
    max_rows: int = 8,
) -> dict[str, Any]:
    """Select a compact report table preview for notebook display."""

    selected_columns = [column for column in columns if column in frame.columns]
    table = frame.loc[:, selected_columns].head(max_rows).copy()
    return {
        "summary": {
            "rows": int(len(frame)),
            "shown_columns": selected_columns,
        },
        "table": table,
    }


def write_public_driven_report_fixture(output_dir: str | Path) -> dict[str, Path]:
    """Write docs-safe synthetic Driven report artifacts."""

    return _write_public_driven_report_fixture(Path(output_dir))


def write_public_eigenmode_report_fixture(output_dir: str | Path) -> dict[str, Path]:
    """Write docs-safe synthetic Eigenmode report artifacts."""

    return _write_public_eigenmode_report_fixture(Path(output_dir))


def write_public_electrostatic_report_fixture(output_dir: str | Path) -> dict[str, Path]:
    """Write docs-safe synthetic Electrostatic report artifacts."""

    return _write_public_electrostatic_report_fixture(Path(output_dir))


def local_palace_run_settings(
    environ: Mapping[str, str] | None = None,
) -> tuple[dict[str, Any], str | None]:
    """Return optional local Palace run kwargs or a docs-safe skip reason."""

    run_kwargs, solver = _solver_env(os.environ if environ is None else environ)
    return run_kwargs, solver["skip_reason"]


def run_public_driven_local_smoke(
    output_dir: str | Path,
    run_kwargs: Mapping[str, Any],
) -> dict[str, Any]:
    """Run the public Driven fixture through a configured local Palace executable."""

    from gsim.palace import load_driven_report

    output_dir = Path(output_dir)
    sim, mesh_result = build_public_driven_cpw_sim(output_dir)
    sim.write_config(
        postprocessing=build_public_driven_postprocessing(mesh_result),
        validate_mesh=False,
        material_overlay=get_gsim_material_overlay(),
        hints=public_solver_config_hints(),
    )
    results = sim.run_local(**dict(run_kwargs))
    report = load_driven_report(output_dir)
    return {
        "problem_type": "Driven",
        "port_names": list(report.sparams.port_names),
        "frequency_points": int(len(report.sparams.freq)),
        "port_epr_rows": int(len(report.port_epr)),
        "source_rows": int(len(report.sources)),
        "has_port_s": "port-S.csv" in results.files,
        "port_s_bytes": int(results.files["port-S.csv"].stat().st_size),
    }


def _apply_public_eigenmode_local_smoke_profile(sim: Any) -> None:
    sim.set_numerical(order=1, tolerance=1e-4, max_iterations=200)
    sim.set_eigenmode(num_modes=1, target=6e9, tolerance=1e-3)


def run_public_eigenmode_local_smoke(
    output_dir: str | Path,
    run_kwargs: Mapping[str, Any],
) -> dict[str, Any]:
    """Run the public Eigenmode fixture through a configured local Palace executable."""

    from gsim.palace import load_eigenmode_report

    output_dir = Path(output_dir)
    sim, mesh_result = build_public_eigenmode_resonator_sim(output_dir)
    _apply_public_eigenmode_local_smoke_profile(sim)
    sim.write_config(
        postprocessing=build_public_eigenmode_postprocessing(mesh_result),
        validate_mesh=False,
        material_overlay=get_gsim_material_overlay(),
        hints=public_solver_config_hints(),
    )
    results = sim.run_local(**dict(run_kwargs))
    report = load_eigenmode_report(results)
    return {
        "problem_type": "Eigenmode",
        "mode_count": int(report.eigenmodes.n_modes),
        "min_frequency_ghz": float(report.eigenmodes.freq_real_ghz.min()),
        "domain_energy_rows": int(len(report.domain_energy)),
        "eig_bytes": int(results["eig.csv"].stat().st_size),
    }


def run_public_electrostatic_local_smoke(
    output_dir: str | Path,
    run_kwargs: Mapping[str, Any],
) -> dict[str, Any]:
    """Run the public Electrostatic fixture through a configured local Palace executable."""

    from gsim.palace import load_electrostatic_report

    output_dir = Path(output_dir)
    sim, mesh_result = build_public_electrostatic_capacitor_sim(output_dir)
    sim.write_config(
        postprocessing=build_public_electrostatic_postprocessing(mesh_result),
        validate_mesh=False,
        material_overlay=get_gsim_material_overlay(),
        hints=public_solver_config_hints(),
    )
    results = sim.run_local(**dict(run_kwargs))
    report = load_electrostatic_report(results)
    return {
        "problem_type": "Electrostatic",
        "terminal_names": list(report.capacitance.terminal_names),
        "matrix_shape": list(report.capacitance.dataframe.shape),
        "has_mutual_matrix": report.mutual_capacitance is not None,
        "has_inverse_matrix": report.inverse_capacitance is not None,
        "terminal_c_bytes": int(results["terminal-C.csv"].stat().st_size),
    }


def _cad_mesh_identity_problem_evidence(
    source: Path,
    *,
    problem_type: str,
    fixture_name: str,
    relative_to: Path | None,
) -> dict[str, Any]:
    manifest = _manifest_identity_evidence(source)
    lookup = _index_map_lookup_evidence(source)
    config = _config_generation_evidence(source)
    lookup_rows = lookup["lookups"]
    rows_without_physical_name = [
        row["entry_name"] for row in lookup_rows if not row.get("physical_name")
    ]
    rows_missing_reverse_lookup = [
        row["entry_name"]
        for row in lookup_rows
        if row["index"] not in row.get("reverse_indices_for_physical_name", ())
    ]
    rows_missing_attribute_lookup = [
        row["entry_name"]
        for row in lookup_rows
        if row.get("attribute") is not None
        and row["entry_name"] not in row.get("entry_names_for_attribute", ())
    ]
    port_names = sorted(
        {
            str(row["metadata"]["port"])
            for row in lookup_rows
            if isinstance(row.get("metadata"), Mapping) and row["metadata"].get("port") is not None
        }
    )
    terminal_names = sorted(
        {str(row["terminal_name"]) for row in lookup_rows if row.get("terminal_name") is not None}
    )
    covered_contracts = [
        "mesh_manifest_schema",
        "mesh_manifest_roles",
        "mesh_manifest_physical_names",
        "palace_index_forward_lookup",
        "palace_index_reverse_lookup",
        "palace_attribute_lookup",
        "config_domain_material_join",
    ]
    if manifest["interface_entry_count"]:
        covered_contracts.append("meshwell_style_interface_identity")
    if port_names:
        covered_contracts.append("port_metadata")
    if terminal_names:
        covered_contracts.append("terminal_metadata")

    return {
        "problem_type": problem_type,
        "fixture": fixture_name,
        "output_dir": (
            _relative_path(source, relative_to) if relative_to is not None else source.as_posix()
        ),
        "artifact_paths": {
            name: (
                _relative_path(source / name, relative_to)
                if relative_to is not None
                else (source / name).as_posix()
            )
            for name in ("mesh_manifest.json", "palace_index_map.json", "config.json")
        },
        "mesh_manifest": manifest,
        "index_map": {
            "schema_version": lookup["schema_version"],
            "entry_count": lookup["row_count"],
            "sections": _count_values([row["section"] for row in lookup_rows]),
            "roles": _count_values([row["role"] for row in lookup_rows]),
            "rows_without_physical_name": rows_without_physical_name,
            "rows_missing_reverse_lookup": rows_missing_reverse_lookup,
            "rows_missing_attribute_lookup": rows_missing_attribute_lookup,
            "port_names": port_names,
            "terminal_names": terminal_names,
        },
        "config_generation": {
            "problem_type": config["problem_type"],
            "solver_problem_block": config["solver_problem_block"],
            "domain_material_count": config["domain_material_count"],
            "domain_material_rows": len(config["domain_materials"]),
            "domain_postprocessing_energy_count": config["domain_postprocessing_energy_count"],
            "surface_flux_count": config["surface_flux_count"],
            "terminal_count": config["terminal_count"],
            "dielectric_postprocessing_count": config["dielectric_postprocessing_count"],
        },
        "covered_contracts": covered_contracts,
        "identity_status": (
            "covered_public_fixture"
            if not rows_without_physical_name
            and not rows_missing_reverse_lookup
            and not rows_missing_attribute_lookup
            else "needs_attention"
        ),
    }


def _build_cad_mesh_identity_handoff_evidence_from_outputs(
    output_root: Path,
    problems: Mapping[str, Mapping[str, Any]],
    *,
    relative_to: Path | None,
) -> dict[str, Any]:
    selected: dict[str, Any] = {}
    for problem_key in PUBLIC_CAD_MESH_IDENTITY_PROBLEM_KEYS:
        problem = problems[problem_key]
        source = output_root / str(problem["output_dir"])
        selected[problem_key] = _cad_mesh_identity_problem_evidence(
            source,
            problem_type=str(problem["problem_type"]),
            fixture_name=str(problem["fixture"]),
            relative_to=relative_to,
        )

    evidence = {
        "schema_version": 1,
        "workflow": "public-cad-mesh-identity-handoff",
        "scope": "Driven, Eigenmode, and Electrostatic public fixture artifacts",
        "repo": "orpen-sc-pdk",
        "owner_boundaries": {
            "meshwell": (
                "solver-agnostic physical names, interface/exterior tag grammar, "
                "XAO/CAD export, and backend equivalence"
            ),
            "gsim": (
                "Palace mesh manifests, config fragments, index maps, and "
                "report/postprocessing lookup"
            ),
            "orpen-sc-pdk": (
                "public PDK layer/material labels, publication-safe fixtures, "
                "notebook evidence, and issue traceability"
            ),
        },
        "deferred_scope": [
            "Magnetostatic report contract",
            "real private HPC/profile validation",
            "upstream meshwell backend-equivalence contract promotion",
        ],
        "upstream_gap": (
            "Current meshwell physical-name/interface-tag contract rows and the "
            "meshwell-to-gsim handoff fixture gate are covered; richer generated "
            "fixtures are future work only if the upstream contract expands."
        ),
        "problems": selected,
    }
    evidence_path = output_root / CAD_MESH_IDENTITY_HANDOFF_FILENAME
    evidence["evidence_path"] = (
        _relative_path(evidence_path, relative_to)
        if relative_to is not None
        else evidence_path.as_posix()
    )
    evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    return evidence


def build_public_cad_mesh_identity_handoff_evidence(
    output_root: str | Path = DEFAULT_OUTPUT_DIR / "cad-mesh-identity-handoff",
    *,
    relative_to: str | Path | None = None,
) -> dict[str, Any]:
    """Build publication-safe CAD/mesh identity handoff evidence."""

    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    relative_root = Path(relative_to) if relative_to is not None else None
    problems: dict[str, dict[str, Any]] = {}
    for spec in _public_core_problem_specs():
        output_dir = output_root / str(spec["problem_key"])
        sim, mesh_result = spec["build_sim"](output_dir)
        sim.write_config(
            postprocessing=spec["build_postprocessing"](mesh_result),
            validate_mesh=False,
            material_overlay=get_gsim_material_overlay(),
            hints=public_solver_config_hints(),
        )
        problems[str(spec["problem_key"])] = {
            "problem_type": spec["problem_type"],
            "fixture": spec["fixture_name"],
            "output_dir": _relative_path(output_dir, output_root),
        }

    return _build_cad_mesh_identity_handoff_evidence_from_outputs(
        output_root,
        problems,
        relative_to=relative_root,
    )


def public_cad_mesh_identity_handoff_table(
    output_root: str | Path = DEFAULT_OUTPUT_DIR / "cad-mesh-identity-handoff",
) -> Any:
    """Return CAD/mesh identity handoff evidence as a notebook table."""

    import pandas as pd

    evidence = build_public_cad_mesh_identity_handoff_evidence(output_root)
    rows = []
    for problem in evidence["problems"].values():
        mesh_manifest = problem["mesh_manifest"]
        index_map = problem["index_map"]
        rows.append(
            {
                "problem_type": problem["problem_type"],
                "fixture": problem["fixture"],
                "identity_status": problem["identity_status"],
                "mesh_roles": mesh_manifest["roles"],
                "interface_physical_names": mesh_manifest["interface_physical_names"],
                "index_sections": index_map["sections"],
                "port_names": index_map["port_names"],
                "terminal_names": index_map["terminal_names"],
                "covered_contracts": problem["covered_contracts"],
                "upstream_gap": evidence["upstream_gap"],
            }
        )
    return pd.DataFrame(rows)


def _public_magnetostatic_cpw_sim(output_dir: Path):
    from gsim.palace import MagnetostaticSim

    component = cpw_straight(length=300, signal_width=10, gap=6, ground_width=40)

    sim = MagnetostaticSim()
    sim.set_output_dir(output_dir)
    sim.set_geometry(component)
    sim.set_stack(
        include_substrate=True,
        substrate_thickness=20,
        add_oxide_dielectric=False,
        add_passivation_dielectric=False,
    )
    sim.set_airbox(margin_x=40, margin_y=40, z_above=50, z_below=10)
    sim.add_current_source(
        "signal",
        layer="D0_TOP_M1",
        center=(0, 0),
        direction=[1.0, 0.0, 0.0],
        coordinate_system="Cartesian",
    )
    sim.add_current_source(
        "return",
        elements=(
            {
                "layer": "D0_TOP_M1",
                "center": (0, 31),
                "direction": "-X",
            },
            {
                "layer": "D0_TOP_M1",
                "center": (0, -31),
                "direction": [-1.0, 0.0, 0.0],
                "coordinate_system": "Cartesian",
            },
        ),
    )
    sim.set_magnetostatic(save_fields=0)
    sim.mesh(
        preset="coarse",
        refined_mesh_size=20,
        max_mesh_size=200,
        margin_x=40,
        margin_y=40,
        planar_conductors=True,
        auto_size=False,
    )
    return sim, sim._last_mesh_result


def _magnetostatic_postprocessing(mesh_result: Any) -> Any:
    from gsim.palace.mesh import build_postprocessing_config_from_manifest

    return build_postprocessing_config_from_manifest(
        mesh_result.manifest,
        include_empty_sections=False,
    )


def _magnetostatic_report_summary(_output_dir: Path) -> dict[str, Any]:
    return {
        "status": "not_implemented",
        "reason": "Magnetostatic report loader is pending a confirmed Palace output contract.",
    }


def _build_problem_evidence(
    *,
    output_root: Path,
    problem_key: str,
    fixture_name: str,
    problem_type: str,
    build_sim: Callable[[Path], tuple[Any, Any]],
    build_postprocessing: Callable[[Any], dict[str, Any]],
    report_summary: Callable[[Path], dict[str, Any]],
    run_kwargs: Mapping[str, Any],
    solver_skip_reason: str | None,
    solver_enabled: bool = True,
    prepare_local_solver: Callable[[Any], None] | None = None,
) -> dict[str, Any]:
    from gsim.palace.handoff import (
        PalaceSlurmSbatchSpec,
        load_palace_slurm_profile_catalog,
        resolve_palace_slurm_profile,
        write_palace_run_handoff_archive_manifest,
        write_palace_slurm_sbatch_handoff,
    )
    from gsim.palace.results import (
        load_palace_run_summary,
        write_palace_resource_record,
        write_palace_resource_record_from_log,
    )

    output_dir = output_root / problem_key
    effective_solver_skip_reason = solver_skip_reason
    if not solver_enabled and effective_solver_skip_reason is None:
        effective_solver_skip_reason = (
            f"{problem_type} local Palace solve deferred by current scope"
        )
    num_processes = int(run_kwargs.get("num_processes", 1) or 1)
    num_threads = int(run_kwargs.get("num_threads", 1) or 1)
    slurm_profiles = load_palace_slurm_profile_catalog(PUBLIC_SLURM_PROFILE_CATALOG)
    slurm_profile = resolve_palace_slurm_profile(
        slurm_profiles,
        "public-slurm-dry-run",
        resource_overrides=_public_slurm_resource_overrides(
            num_processes=num_processes,
            num_threads=num_threads,
        ),
    )
    sim, mesh_result = build_sim(output_dir)
    if effective_solver_skip_reason is None and prepare_local_solver is not None:
        prepare_local_solver(sim)
    sim.write_config(
        postprocessing=build_postprocessing(mesh_result),
        validate_mesh=False,
        material_overlay=get_gsim_material_overlay(),
        hints=slurm_profile.to_palace_config_hints(),
    )
    write_palace_slurm_sbatch_handoff(
        output_dir,
        PalaceSlurmSbatchSpec(
            job_name=f"palace_{problem_key}",
            resources=slurm_profile.resources,
            **slurm_profile.launcher.to_sbatch_kwargs(),
        ),
        profile=slurm_profile.profile,
        metadata={
            "fixture": fixture_name,
            "problem_type": problem_type,
            "solver_enabled": effective_solver_skip_reason is None,
            "workflow": "public-palace-smoke-evidence",
        },
    )
    write_palace_run_handoff_archive_manifest(
        output_dir,
        metadata={
            "fixture": fixture_name,
            "problem_type": problem_type,
            "workflow": "public-palace-smoke-evidence",
        },
    )
    if effective_solver_skip_reason is not None:
        _write_public_log_resource_record(
            write_palace_resource_record_from_log,
            output_dir=output_dir,
            fixture_name=fixture_name,
            problem_type=problem_type,
            run_kwargs=run_kwargs,
            status="synthetic",
            missing_sources=(effective_solver_skip_reason,),
        )
    run_summary = _relative_run_summary(
        load_palace_run_summary(output_dir, include_hashes=True).to_dict(),
        output_root,
    )

    if effective_solver_skip_reason is None:
        sim.run_local(**dict(run_kwargs))
        completed_summary = load_palace_run_summary(output_dir, include_hashes=True)
        _write_public_resource_record(
            write_palace_resource_record,
            output_dir=output_dir,
            fixture_name=fixture_name,
            problem_type=problem_type,
            run_kwargs=run_kwargs,
            status="completed",
            runtime_summary=completed_summary.runtime,
            missing_sources=(),
        )
        run_summary = _relative_run_summary(
            load_palace_run_summary(output_dir, include_hashes=True).to_dict(),
            output_root,
        )
        solver_report = report_summary(output_dir)
    else:
        solver_report = {"status": "skipped", "reason": effective_solver_skip_reason}

    return {
        "problem_type": problem_type,
        "fixture": fixture_name,
        "output_dir": _relative_path(output_dir, output_root),
        "run_summary": run_summary,
        "config_generation": _config_generation_evidence(output_dir),
        "index_map_lookup": _index_map_lookup_evidence(output_dir),
        "solver_report": solver_report,
    }


def _build_sweep_evidence(
    output_root: Path,
    problems: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    from gsim.palace.handoff import (
        PalaceSlurmSweepArraySpec,
        load_palace_slurm_profile_catalog,
        resolve_palace_slurm_profile,
        write_palace_slurm_sweep_array_handoff,
        write_palace_sweep_handoff_archive_manifest,
    )
    from gsim.palace.results import (
        PalaceSweepPointSpec,
        load_palace_sweep_summary,
        write_palace_sweep_points,
        write_palace_sweep_resource_index,
    )

    points = [
        PalaceSweepPointSpec(
            point_slug=problem_key,
            parameters={
                "problem_type": problem["problem_type"],
                "fixture": problem["fixture"],
            },
            run_dir=problem["output_dir"],
            handoff_metadata_path=(f"{problem['output_dir']}/palace_handoff_metadata.json"),
            resource_record_path=(
                f"{problem['output_dir']}/metadata/records/palace_resource_record.json"
            ),
        )
        for problem_key, problem in sorted(problems.items())
    ]
    write_palace_sweep_points(
        output_root,
        points,
        sweep_id="public_palace_problem_type_smoke",
    )
    slurm_profiles = load_palace_slurm_profile_catalog(PUBLIC_SLURM_PROFILE_CATALOG)
    slurm_profile = resolve_palace_slurm_profile(
        slurm_profiles,
        "public-slurm-sweep-dry-run",
    )
    write_palace_slurm_sweep_array_handoff(
        output_root,
        PalaceSlurmSweepArraySpec(
            job_name="palace_public_problem_smoke",
            resources=slurm_profile.resources,
            max_parallel=len(points),
            **slurm_profile.launcher.to_sbatch_kwargs(),
        ),
        profile=slurm_profile.profile,
        metadata={
            "workflow": "public-palace-smoke-evidence",
            "point_count": len(points),
        },
    )
    write_palace_sweep_handoff_archive_manifest(
        output_root,
        metadata={
            "workflow": "public-palace-smoke-evidence",
            "point_count": len(points),
        },
    )
    sweep_summary = _relative_sweep_summary(
        load_palace_sweep_summary(
            output_root,
            include_hashes=True,
            include_report_metrics=True,
        ).to_dict(),
        output_root,
    )
    resource_index = write_palace_sweep_resource_index(
        output_root,
        include_hashes=True,
        include_report_metrics=True,
    )
    return {
        "summary": sweep_summary,
        "resource_index": _relative_result_paths(resource_index.to_dict(), output_root),
    }


def _write_public_resource_record(
    writer: Callable[..., Path],
    *,
    output_dir: Path,
    fixture_name: str,
    problem_type: str,
    run_kwargs: Mapping[str, Any],
    status: str,
    runtime_summary: Mapping[str, Any] | None,
    missing_sources: Sequence[str],
) -> None:
    num_processes = int(run_kwargs.get("num_processes", 1) or 1)
    num_threads = int(run_kwargs.get("num_threads", 1) or 1)
    runtime: dict[str, Any] = {}
    launcher: dict[str, Any] = {}
    if runtime_summary:
        runtime["return_code"] = runtime_summary.get("return_code")
        if runtime_summary.get("elapsed_seconds") is not None:
            runtime["wall_time_seconds"] = runtime_summary["elapsed_seconds"]
        launcher = dict(runtime_summary.get("launcher", {}) or {})

    writer(
        output_dir,
        status=status,
        launcher=launcher,
        allocation={
            "nodes": 1,
            "num_processes": num_processes,
            "num_threads": num_threads,
            "cores": num_processes * num_threads,
        },
        runtime=runtime,
        missing_sources=missing_sources,
        metadata={
            "fixture": fixture_name,
            "problem_type": problem_type,
            "workflow": "public-palace-smoke-evidence",
            "measured": status == "completed",
        },
    )


def _write_public_log_resource_record(
    writer: Callable[..., Path],
    *,
    output_dir: Path,
    fixture_name: str,
    problem_type: str,
    run_kwargs: Mapping[str, Any],
    status: str,
    missing_sources: Sequence[str],
) -> None:
    num_processes = int(run_kwargs.get("num_processes", 1) or 1)
    num_threads = int(run_kwargs.get("num_threads", 1) or 1)
    log_path = _write_public_palace_resource_log(
        output_dir,
        num_processes=num_processes,
        num_threads=num_threads,
    )
    scontrol_path = _write_public_slurm_scontrol(
        output_dir,
        num_processes=num_processes,
        num_threads=num_threads,
    )
    writer(
        output_dir,
        log_path,
        scontrol_path=scontrol_path,
        status=status,
        allocation={
            "nodes": 1,
            "num_processes": num_processes,
            "num_threads": num_threads,
            "cores": num_processes * num_threads,
        },
        missing_sources=missing_sources,
        metadata={
            "fixture": fixture_name,
            "measured": False,
            "problem_type": problem_type,
            "resource_log_source": "synthetic-public-fixture",
            "workflow": "public-palace-smoke-evidence",
        },
    )


def _write_public_palace_resource_log(
    output_dir: Path,
    *,
    num_processes: int,
    num_threads: int,
) -> Path:
    log_path = output_dir / "logs" / "palace-public-resource.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        dedent(
            f"""
            Git changeset ID: v0.16.1
            Running with {num_processes} MPI processes, {num_threads} OpenMP threads
            Device configuration: omp,cpu
            Memory configuration: host-std
            libCEED backend: /cpu/self/xsmm/blocked

            Cumulative timing statistics:

            Elapsed Time Report (s)           Min.        Max.        Avg.
            ==============================================================
            Initialization                   1.000       1.100       1.050
            Operator Construction            2.000       2.200       2.100
            Disk IO                          0.400       0.500       0.450
            --------------------------------------------------------------
            Total                           58.573      58.580      58.578

            Peak Memory                   Per-Node       Total   Total HWM
            ==============================================================
            Initialization                   79.1M       79.1M       79.1M
            Operator Construction             1.6G        1.6G        2.0G
            Disk IO                         216.9M      216.9M        2.1G
            --------------------------------------------------------------
            Total                            10.8G       10.8G       10.8G
            Estimated peak per-rank memory usage is: Min. 2.7G, Max. 2.7G, Avg. 2.7G, Total 10.9G
            Estimated peak per-node memory usage is: Min. 10.9G, Max. 10.9G, Avg. 10.9G, Total 10.9G

            Adaptive mesh refinement (AMR) iteration 1:
             Indicator norm = 3.158e-01, global unknowns = 887970
             Max. iterations = 15, tol. = 1.000e-02, max. size = 5000000
             Marked 12568/664696 elements for refinement (70.00% of the error, theta = 0.70)
             Conforming mesh refinement added 659265 elements (initial = 664696, final = 1323961)

            Proceeding with solve/estimate iteration 2...

            Elapsed Time Report (s)           Min.        Max.        Avg.
            ==============================================================
            Initialization                   1.000       1.100       1.050
            Operator Construction            3.000       3.200       3.100
            Disk IO                          0.400       0.500       0.450
            --------------------------------------------------------------
            Total                          120.000     121.000     120.500

            Peak Memory                   Per-Node       Total   Total HWM
            ==============================================================
            Initialization                   79.1M       79.1M       79.1M
            Operator Construction             2.6G        2.6G        3.0G
            Disk IO                         216.9M      216.9M        3.1G
            --------------------------------------------------------------
            Total                            20.8G       20.8G       20.8G
            Estimated peak per-rank memory usage is: Min. 5.2G, Max. 5.2G, Avg. 5.2G, Total 20.9G
            Estimated peak per-node memory usage is: Min. 20.9G, Max. 20.9G, Avg. 20.9G, Total 20.9G

            Completed 1 iterations of adaptive mesh refinement (AMR):
             Indicator norm = 1.522e-01, global unknowns = 10718029
             Max. iterations = 15, tol. = 1.000e-02, max. size = 5000000

            ---------- PETSc Performance Summary: ----------

            palace on a  named public-node with {num_processes} processes, by user on 2026-05-21
            Using {num_threads} OpenMP threads
            Using PETSc Release Version 3.24.3, unknown

                                     Max       Max/Min     Avg       Total
            Time (sec):           1.029e+03     1.000   1.029e+03
            """
        )
    )
    return log_path


def _write_public_slurm_scontrol(
    output_dir: Path,
    *,
    num_processes: int,
    num_threads: int,
) -> Path:
    scontrol_path = output_dir / "metadata" / "scontrol-job-public.txt"
    scontrol_path.parent.mkdir(parents=True, exist_ok=True)
    num_cpus = num_processes * num_threads
    scontrol_path.write_text(
        dedent(
            f"""
            JobId=12345 JobName=public_palace_fixture
               Account=public_alloc JobState=COMPLETED
               SubmitTime=2026-05-21T18:16:44 StartTime=2026-05-21T18:24:47
               EndTime=2026-05-21T18:26:48
               Partition=public_cpu NodeList=public-node BatchHost=public-node
               NumNodes=1 NumCPUs={num_cpus} NumTasks={num_processes}
               CPUs/Task={num_threads} TimeLimit=00:10:00 RunTime=00:02:01
               TRES=cpu={num_cpus},mem=1024M,node=1,billing={num_cpus}
            """
        )
    )
    return scontrol_path


def build_public_palace_smoke_evidence(
    output_root: str | Path = DEFAULT_OUTPUT_DIR,
    *,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Build publication-safe public Palace smoke evidence for local review."""

    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    environ = os.environ if environ is None else environ
    run_kwargs, solver = _solver_env(environ)

    orpen_sc_pdk.activate()
    problems = {
        spec["problem_key"]: _build_problem_evidence(
            output_root=output_root,
            problem_key=spec["problem_key"],
            fixture_name=spec["fixture_name"],
            problem_type=spec["problem_type"],
            build_sim=spec["build_sim"],
            build_postprocessing=spec["build_postprocessing"],
            report_summary=spec["report_summary"],
            run_kwargs=run_kwargs,
            solver_skip_reason=solver["skip_reason"],
            solver_enabled=spec["solver_enabled"],
            prepare_local_solver=spec["prepare_local_solver"],
        )
        for spec in _public_problem_specs()
    }
    sweep_evidence = _build_sweep_evidence(output_root, problems)
    cad_mesh_identity_handoff = _build_cad_mesh_identity_handoff_evidence_from_outputs(
        output_root,
        problems,
        relative_to=output_root,
    )
    gsim_boundary_review_coverage = build_public_gsim_boundary_review_coverage_evidence(
        output_root / "gsim-boundary-review-coverage",
        relative_to=output_root,
    )
    meshwell_handoff_contract_gate = build_public_meshwell_handoff_contract_gate_evidence(
        output_root / "meshwell-handoff-contract-gate",
        relative_to=output_root,
    )
    interface_preset_promotion_gate = build_public_interface_preset_promotion_gate_evidence(
        output_root / "interface-preset-promotion-gate",
        relative_to=output_root,
    )
    thin_film_proxy_evidence = build_public_thin_film_sheet_proxy_interface_evidence(
        output_root / "thin-film-sheet-proxy-interface",
        relative_to=output_root,
    )

    evidence = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "workflow": "public-palace-smoke-evidence",
        "repo": "orpen-sc-pdk",
        "solver": solver,
        "helper_node_inventory": load_public_simulation_helper_node_inventory(),
        "problem_notebook_crosscheck": load_public_problem_notebook_crosscheck(),
        "goal_audit": load_public_simulation_goal_audit(),
        "gsim_boundary_review_crosscheck": load_public_gsim_boundary_review_crosscheck(),
        "gsim_boundary_review_coverage": gsim_boundary_review_coverage,
        "meshwell_handoff_contract_gate": meshwell_handoff_contract_gate,
        "interface_preset_review_queue": load_public_interface_preset_review_queue(),
        "cad_mesh_identity_handoff": cad_mesh_identity_handoff,
        "interface_preset_promotion_gate": interface_preset_promotion_gate,
        "thin_film_sheet_proxy_interface": thin_film_proxy_evidence,
        "problems": problems,
        "sweep_summary": sweep_evidence["summary"],
        "sweep_resource_index": sweep_evidence["resource_index"],
    }

    evidence_path = output_root / EVIDENCE_FILENAME
    evidence["evidence_path"] = _relative_path(evidence_path, output_root)
    evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    return evidence


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build public OrPen/gsim Palace smoke evidence artifacts.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Evidence output directory. Defaults to {DEFAULT_OUTPUT_DIR}.",
    )
    args = parser.parse_args(argv)

    evidence = build_public_palace_smoke_evidence(args.output_dir)
    print(args.output_dir / evidence["evidence_path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
