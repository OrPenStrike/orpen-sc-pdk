from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import scripts.public_palace_smoke_evidence as smoke_evidence
from scripts.public_palace_smoke_evidence import (
    EVIDENCE_FILENAME,
    _driven_report_summary,
    build_public_cad_mesh_identity_handoff_evidence,
    build_public_gsim_boundary_review_coverage_evidence,
    build_public_interface_preset_promotion_gate_evidence,
    build_public_meshwell_handoff_contract_gate_evidence,
    build_public_palace_smoke_evidence,
    build_public_thin_film_sheet_proxy_interface_evidence,
    load_public_gsim_boundary_review_crosscheck,
    load_public_interface_preset_review_queue,
    load_public_problem_notebook_crosscheck,
    load_public_simulation_goal_audit,
    load_public_simulation_helper_node_inventory,
)


def _assert_index_map_lookup_round_trip(problem: dict) -> list[dict]:
    lookup = problem["index_map_lookup"]
    rows = lookup["lookups"]

    assert lookup["schema_version"] == 1
    assert lookup["row_count"] == problem["run_summary"]["index_map"]["entry_count"]
    assert rows
    for row in rows:
        assert row["physical_name"]
        assert row["index"] in row["reverse_indices_for_physical_name"]
        if row["attribute"] is not None:
            assert row["entry_name"] in row["entry_names_for_attribute"]
    return rows


def _assert_config_generation_material_provenance(problem: dict) -> list[dict]:
    config_generation = problem["config_generation"]
    rows = config_generation["domain_materials"]

    assert config_generation["problem_type"] == problem["problem_type"]
    assert config_generation["solver_device"] == "CPU"
    assert config_generation["solver_has_linear"] is True
    assert config_generation["solver_problem_block"] == problem["problem_type"]
    assert config_generation["domain_material_count"] == 2
    assert config_generation["material_resolution"] == {
        "schema_version": 1,
        "material_count": 2,
        "interface_count": 0,
    }
    assert len(rows) == config_generation["domain_material_count"]

    by_stack_material = {row["stack_material_name"]: row for row in rows}
    silicon = by_stack_material["silicon"]
    assert silicon["matched_material_name"] == "silicon"
    assert silicon["material_model_source"] == "orpen-sc-pdk tech.material_properties"
    assert silicon["material_within_validity"] is True
    assert silicon["permittivity"] == pytest.approx(11.45)
    assert silicon["conductivity"] == pytest.approx(2.0)
    assert silicon["permeability"] == pytest.approx(1.0)

    air = by_stack_material["air"]
    assert air["matched_material_name"] == "air"
    assert air["material_model_source"] == "orpen-sc-pdk tech.material_properties"
    assert air["permittivity"] == pytest.approx(1.0)
    assert air["loss_tangent"] == pytest.approx(0.0)
    assert air["permeability"] == pytest.approx(1.0)
    return rows


def _assert_helper_node_inventory(evidence: dict) -> None:
    rows = evidence["helper_node_inventory"]
    assert rows == load_public_simulation_helper_node_inventory()
    assert len(rows) >= 10

    by_node = {row["node"]: row for row in rows}
    assert by_node["Driven problem fixture"]["public_status"] == "implemented_public_fixture"
    assert by_node["Eigenmode problem fixture"]["gdsfactory_home"] == "gsim"
    assert by_node["Electrostatic problem fixture"]["next_issue"] == (
        "public-problem-type-notebook-coverage"
    )

    magnetostatic = by_node["Magnetostatic problem fixture"]
    assert (
        magnetostatic["public_status"] == "implemented_public_config_fixture_pending_report_loader"
    )
    assert (
        magnetostatic["promotion_gate"] == "report_loader_requires_confirmed_palace_output_contract"
    )
    assert "Magnetostatic Palace CSV/output schema" in magnetostatic["missing_evidence"]
    assert "MagnetostaticSim" in magnetostatic["public_api_or_artifact"]
    assert "SurfaceCurrent" in magnetostatic["private_capability"]

    interface = by_node["Dielectric interface MA/MS/SA classification"]
    assert interface["promotion_gate"] == "source_backed_public_default_policy_required"
    assert "accepted public MA/MS/SA preset records" in interface["missing_evidence"]
    assert "thin-film conductor-sheet MA/MS proxy" in interface["private_capability"]

    for row in rows:
        assert row["node"]
        assert row["private_anchor"]
        assert row["why_helper_exists"]
        assert row["gdsfactory_home"] in {
            "gsim",
            "orpen-sc-pdk + gsim",
            "meshwell + gsim",
        }
        assert row["promotion_gate"]
        assert row["missing_evidence"]
        assert row["next_issue"]


def _assert_problem_notebook_crosscheck(evidence: dict) -> None:
    rows = evidence["problem_notebook_crosscheck"]
    assert rows == load_public_problem_notebook_crosscheck()

    by_type = {row["problem_type"]: row for row in rows}
    assert {"Driven", "Eigenmode", "Electrostatic"} <= set(by_type)

    expected_notebooks = {
        "Driven": Path("notebooks/src/public_driven_workflow.py"),
        "Eigenmode": Path("notebooks/src/public_eigenmode_workflow.py"),
        "Electrostatic": Path("notebooks/src/public_electrostatic_workflow.py"),
    }
    for problem_type, notebook in expected_notebooks.items():
        row = by_type[problem_type]
        assert Path(row["public_notebook"]) == notebook
        assert notebook.exists()
        assert row["private_representative_notebook"].endswith(".ipynb")
        assert row["public_helper_node"]
        assert row["owner_decision"]
        assert row["gsim_api_or_artifact"]
        assert row["notebook_support_wrapper"]
        assert row["coverage_status"].startswith("covered_public_fixture")
        assert row["next_issue"]

    q2d = by_type["AEDT/Q2D"]
    assert q2d["coverage_status"] == "deferred_owner_pending"
    assert q2d["gdsfactory_home"] == "owner_pending"
    assert q2d["public_notebook"] == ""
    assert "Palace notebook suite" in q2d["gsim_api_or_artifact"]
    assert q2d["notebook_support_wrapper"] == ""
    assert "Deferred owner decision" in q2d["owner_decision"]


def _assert_goal_audit(evidence: dict) -> None:
    rows = evidence["goal_audit"]
    assert rows == load_public_simulation_goal_audit()
    assert len(rows) >= 10

    by_requirement = {row["objective_requirement"]: row for row in rows}
    local_palace_key = (
        "Verify local Palace coarse smoke for the public Driven, Eigenmode, "
        "and Electrostatic fixtures."
    )
    local_palace = by_requirement[local_palace_key]
    assert local_palace["current_status"] == "covered_current"
    assert "Spack-wrapper local replay passed" in local_palace["current_evidence"]
    assert "PALACE_EXECUTABLE" in local_palace["remaining_gap"]

    deferred_scope_key = (
        "Keep Magnetostatic report contract and real HPC/private profile validation "
        "out of the current scope."
    )
    deferred_scope = by_requirement[deferred_scope_key]
    assert deferred_scope["current_status"] == "deferred_user_scope"

    q2d = by_requirement[
        "Handle AEDT/Q2D capabilities without folding them into the Palace notebook suite."
    ]
    assert q2d["current_status"] == "deferred_owner_pending"
    assert "owner_pending" in q2d["current_evidence"]

    interface_gate = by_requirement[
        "Keep MA/MS/SA dielectric-interface preset promotion source-backed and "
        "notebook-visible without publishing defaults prematurely."
    ]
    assert interface_gate["current_status"] == "covered_current"
    assert "public_interface_preset_review_queue.json" in interface_gate["current_evidence"]
    assert "thin-film sheet proxy MA/MS evidence" in interface_gate["current_evidence"]
    assert "tech.interface_preset_records" in interface_gate["remaining_gap"]

    statuses = {row["current_status"] for row in rows}
    assert {
        "covered_current",
        "deferred_user_scope",
        "deferred_owner_pending",
    } <= statuses

    for row in rows:
        assert row["objective_requirement"]
        assert row["current_evidence"]
        assert row["remaining_gap"]
        assert row["next_issue"]


def _assert_gsim_boundary_review_crosscheck(evidence: dict) -> None:
    rows = evidence["gsim_boundary_review_crosscheck"]
    assert rows == load_public_gsim_boundary_review_crosscheck()
    assert len(rows) >= 60

    commits = [row["commit"] for row in rows]
    assert len(commits) == len(set(commits))
    assert commits[0] == "2ab16d7"
    assert commits[-1] == "76f7dc0"

    by_commit = {row["commit"]: row for row in rows}
    assert by_commit["00b2777"]["ecosystem_home"] == "gsim"
    assert "not OrPen or gplugins" in by_commit["00b2777"]["boundary_note"]
    assert by_commit["d996f87"]["boundary_group"] == "api-surface-and-owner-module-cleanup"
    assert by_commit["9b3574a"]["boundary_group"] == "api-surface-and-owner-module-cleanup"
    assert by_commit["883fb78"]["review_status"] == "reviewed_explicit_with_fix"
    assert by_commit["bc78ad4"]["review_status"] == "reviewed_explicit_fix"
    assert by_commit["76f7dc0"]["boundary_group"] == "meshwell-gsim-handoff-contract-gate"

    groups = {row["boundary_group"] for row in rows}
    assert {
        "mesh-index-and-postprocessing-provenance",
        "port-terminal-intent",
        "result-report-loaders",
        "material-overlay-and-interface-provenance",
        "runtime-handoff-and-resource-records",
        "sweep-handoff-and-resource-records",
        "magnetostatic-config-intent",
        "api-surface-and-owner-module-cleanup",
    } <= groups

    for row in rows:
        assert row["commit"]
        assert row["summary"]
        assert row["boundary_group"]
        assert row["review_status"].startswith("reviewed_")
        assert row["ecosystem_home"] in {"gsim", "meshwell + gsim"}
        assert row["owner_surface"]
        assert row["evidence_anchor"].endswith(".md") or ".md;" in row["evidence_anchor"]
        assert row["boundary_note"]


def _assert_gsim_boundary_review_coverage(evidence: dict) -> None:
    coverage = evidence["gsim_boundary_review_coverage"]
    review_rows = load_public_gsim_boundary_review_crosscheck()
    review_commits = [row["commit"] for row in review_rows]

    assert coverage["schema_version"] == 1
    assert coverage["workflow"] == "public-gsim-boundary-review-coverage"
    assert coverage["repo"] == "orpen-sc-pdk"
    assert coverage["output_dir"] == "gsim-boundary-review-coverage"
    assert coverage["evidence_path"] == (
        "gsim-boundary-review-coverage/public_gsim_boundary_review_coverage_evidence.json"
    )
    assert set(coverage["owner_boundaries"]) == {"gsim", "orpen-sc-pdk"}
    assert coverage["local_repo_status"] == "available"
    assert coverage["coverage_status"] == "complete"
    assert coverage["coverage_complete"] is True
    assert coverage["base_ref"] in {"upstream/main", "origin/main"}
    assert coverage["gsim_branch"]
    assert coverage["gsim_head"] == review_commits[-1]
    assert coverage["first_commit"] == review_commits[0]
    assert coverage["last_commit"] == review_commits[-1]
    assert coverage["fixture_commit_count"] == len(review_commits)
    assert coverage["git_log_commit_count"] == len(review_commits)
    assert coverage["reviewed_commit_count"] == len(review_commits)
    assert coverage["local_commit_count"] == len(review_commits)
    assert coverage["covered_commit_count"] == len(review_commits)
    assert coverage["missing_from_fixture"] == []
    assert coverage["extra_in_fixture"] == []
    assert coverage["missing_review_commits"] == []
    assert coverage["stale_review_commits"] == []
    assert coverage["duplicate_fixture_commits"] == []
    assert coverage["duplicate_review_commits"] == []
    assert coverage["invalid_review_rows"] == []
    assert coverage["deferred_scope"] == [
        "Magnetostatic report contract",
        "real HPC/private profile validation",
    ]
    assert coverage["ecosystem_home_counts"]["gsim"] >= 1
    assert coverage["ecosystem_home_counts"]["meshwell + gsim"] >= 1
    assert coverage["boundary_group_counts"]["api-surface-and-owner-module-cleanup"] >= 1
    assert coverage["review_status_counts"]["reviewed_explicit"] >= 1

    rows = coverage["coverage_rows"]
    assert [row["commit"] for row in rows] == review_commits
    assert all(row["local_branch_status"] == "present" for row in rows)
    assert all(str(row["review_status"]).startswith("reviewed_") for row in rows)
    assert all(row["evidence_anchor"] for row in rows)


def _assert_meshwell_handoff_contract_gate(evidence: dict) -> None:
    gate = evidence["meshwell_handoff_contract_gate"]

    assert gate["schema_version"] == 1
    assert gate["workflow"] == "public-meshwell-handoff-contract-gate"
    assert gate["repo"] == "orpen-sc-pdk"
    assert gate["output_dir"] == "meshwell-handoff-contract-gate"
    assert gate["evidence_path"] == (
        "meshwell-handoff-contract-gate/public_meshwell_handoff_contract_gate_evidence.json"
    )
    assert set(gate["owner_boundaries"]) == {"meshwell", "gsim", "orpen-sc-pdk"}
    assert gate["contract_status"] == "formal_contract_and_cross_repo_gate_aligned"
    assert gate["evidence_status_counts"] == {
        "covered_cross_repo_consumer_fixture": 2,
        "covered_gsim_consumer_parser": 5,
        "covered_meshwell_backend_equivalence": 3,
        "covered_source": 7,
    }
    assert gate["covered_source_count"] == 7
    assert gate["covered_meshwell_backend_equivalence_count"] == 3
    assert gate["covered_gsim_consumer_parser_count"] == 5
    assert gate["covered_cross_repo_consumer_fixture_count"] == 2
    assert gate["covered_count"] == 17
    assert gate["pending_count"] == 0
    assert gate["blocking_gaps"] == []

    rows = gate["gate_rows"]
    by_item = {row["contract_item"]: row for row in rows}
    assert (
        by_item["meshwell cad_gmsh interface/exterior naming docstring"]["evidence_status"]
        == "covered_source"
    )
    assert by_item["meshwell cad_gmsh delimiter defaults"]["evidence_status"] == ("covered_source")
    assert by_item["meshwell mesh delimiter defaults"]["evidence_status"] == ("covered_source")
    assert (
        by_item["meshwell OCC XAO writer physical-group serializer"]["evidence_status"]
        == "covered_source"
    )
    assert (
        by_item["meshwell multiple physical-name equivalence tests"]["evidence_status"]
        == "covered_source"
    )
    assert (
        by_item["meshwell interface sharing and exterior refinement tests"]["evidence_status"]
        == "covered_source"
    )
    assert (
        by_item["meshwell CAD backend physical-group equivalence tests"]["evidence_status"]
        == "covered_meshwell_backend_equivalence"
    )
    assert (
        by_item["meshwell loaded CAD state backend equivalence tests"]["evidence_status"]
        == "covered_meshwell_backend_equivalence"
    )
    assert (
        by_item["meshwell mesh-level backend cross-compare tests"]["evidence_status"]
        == "covered_meshwell_backend_equivalence"
    )
    assert (
        by_item["gsim manifest parser supports meshwell-style names"]["evidence_status"]
        == "covered_gsim_consumer_parser"
    )
    assert (
        by_item["gsim manifest tests cover interface/exterior parsing"]["evidence_status"]
        == "covered_gsim_consumer_parser"
    )
    assert (
        by_item["gsim postprocessing index-map lookup helpers"]["evidence_status"]
        == "covered_gsim_consumer_parser"
    )
    assert (
        by_item["gsim public postprocessing index-map result loader"]["evidence_status"]
        == "covered_gsim_consumer_parser"
    )
    assert (
        by_item["gsim generated mesh integration tests preserve identities"]["evidence_status"]
        == "covered_gsim_consumer_parser"
    )

    contract_text = by_item["formal meshwell physical-name/interface-tag contract text"]
    assert contract_text["evidence_status"] == "covered_source"
    assert contract_text["relative_path"] == "docs/physical_name_contract.md"
    assert contract_text["missing_signals"] == []
    assert (
        contract_text["remaining_gap"]
        == "covered by the current gsim meshwell-generated MSH handoff fixture"
    )

    cross_repo_gate = by_item["meshwell-to-gsim cross-repo consumer fixture/gate"]
    assert cross_repo_gate["evidence_status"] == "covered_cross_repo_consumer_fixture"
    assert cross_repo_gate["relative_path"] == "tests/palace/test_meshwell_handoff_contract.py"
    assert cross_repo_gate["missing_signals"] == []
    assert cross_repo_gate["remaining_gap"] == (
        "none for the current meshwell-to-gsim consumer gate"
    )

    msh_fixture = by_item["gsim meshwell-generated MSH handoff fixture"]
    assert msh_fixture["evidence_status"] == "covered_cross_repo_consumer_fixture"
    assert (
        msh_fixture["relative_path"]
        == "tests/palace/test_meshwell_handoff_contract/physical_name_contract.msh"
    )
    assert msh_fixture["missing_signals"] == []


def _assert_interface_preset_review_queue(evidence: dict) -> None:
    queue = evidence["interface_preset_review_queue"]
    assert queue == load_public_interface_preset_review_queue()
    assert queue["schema_version"] == 1
    assert queue["owner_repo"] == "orpen-sc-pdk"
    assert "do not populate tech.interface_preset_records" in queue["promotion_policy"]
    assert len(queue["sources"]) >= 4
    assert len(queue["candidate_records"]) >= 7

    source_ids = {row["source_id"] for row in queue["sources"]}
    assert {"Wenner2011", "Woods2019"} <= source_ids

    candidates = queue["candidate_records"]
    roles = {row["role"] for row in candidates}
    assert {"MA", "MS", "SA"} <= roles
    assert all(row["public_default_status"] == "not_public_default" for row in candidates)
    assert all(row["owner_repo"] == "orpen-sc-pdk" for row in candidates)
    assert all(row["promotion_gate"] for row in candidates)
    assert all(row["source_id"] in source_ids for row in candidates)
    assert any(row["promotion_status"] == "not_interface_preset" for row in candidates)

    by_candidate = {row["candidate_record"]: row for row in candidates}
    woods_ms = by_candidate["Woods2019_CPW_Si_MS_candidate"]
    assert woods_ms["role"] == "MS"
    assert woods_ms["public_default_status"] == "not_public_default"
    assert "gsim material-kind/exact assignment helpers" in woods_ms["gsim_handoff"]


def _assert_interface_preset_promotion_gate_evidence(evidence: dict) -> None:
    gate = evidence["interface_preset_promotion_gate"]

    assert gate["schema_version"] == 1
    assert gate["workflow"] == "public-interface-preset-promotion-gate"
    assert gate["repo"] == "orpen-sc-pdk"
    assert gate["output_dir"] == "interface-preset-promotion-gate"
    assert gate["evidence_path"] == (
        "interface-preset-promotion-gate/public_interface_preset_promotion_gate_evidence.json"
    )
    assert set(gate["owner_boundaries"]) == {"orpen-sc-pdk", "gsim"}
    assert gate["default_policy_status"] == "not_defined"
    assert gate["pdk_interface_preset_record_count"] == 0
    assert gate["tech_interface_preset_records_populated"] is False
    assert gate["accepted_interface_candidate_ids"] == []
    assert gate["public_default_candidate_ids"] == []
    assert gate["source_count"] >= 4
    assert gate["candidate_count"] >= 7
    assert gate["interface_candidate_count"] >= 6
    assert {"MA", "MS", "SA"} <= set(gate["role_counts"])
    assert gate["readiness_counts"]["awaiting_public_policy"] >= 6
    assert gate["readiness_counts"]["not_interface_preset"] >= 1
    assert {
        "accepted_candidate_id",
        "process_scope",
        "default_selection_rule",
        "source_id",
        "role",
        "thickness_um",
        "material_or_permittivity",
        "loss_tangent",
        "source_basis",
    } <= set(gate["required_acceptance_fields"])
    assert gate["open_decisions"]

    rows = gate["candidate_gate_rows"]
    assert all(row["public_default_status"] == "not_public_default" for row in rows)
    assert all(row["owner_repo"] == "orpen-sc-pdk" for row in rows)
    interface_rows = [row for row in rows if row["is_interface_preset_candidate"]]
    assert interface_rows
    assert all(row["readiness_status"] == "awaiting_public_policy" for row in interface_rows)
    assert all("process_scope" in row["missing_decisions"] for row in interface_rows)
    assert all("default_selection_rule" in row["missing_decisions"] for row in interface_rows)
    assert all("public_default_decision" in row["missing_decisions"] for row in interface_rows)

    by_candidate = {row["candidate_record"]: row for row in rows}
    woods_ms = by_candidate["Woods2019_CPW_Si_MS_candidate"]
    assert woods_ms["role"] == "MS"
    assert woods_ms["source_review_status"] == "primary_extraction_candidate"
    assert woods_ms["has_thickness"] is True
    assert woods_ms["has_material_or_permittivity"] is True
    assert woods_ms["has_loss_tangent"] is True
    assert woods_ms["readiness_status"] == "awaiting_public_policy"

    bulk = by_candidate["Woods2019_CPW_Si_bulk_candidate"]
    assert bulk["is_interface_preset_candidate"] is False
    assert bulk["readiness_status"] == "not_interface_preset"
    assert bulk["promotion_gate"] == "material_schema_boundary_required"


def _assert_cad_mesh_identity_handoff_evidence(evidence: dict) -> None:
    audit = evidence["cad_mesh_identity_handoff"]

    assert audit["schema_version"] == 1
    assert audit["workflow"] == "public-cad-mesh-identity-handoff"
    assert audit["scope"] == ("Driven, Eigenmode, and Electrostatic public fixture artifacts")
    assert audit["repo"] == "orpen-sc-pdk"
    assert audit["evidence_path"] == "public_cad_mesh_identity_handoff_evidence.json"
    assert set(audit["owner_boundaries"]) == {"meshwell", "gsim", "orpen-sc-pdk"}
    assert "Magnetostatic report contract" in audit["deferred_scope"]
    assert "real private HPC/profile validation" in audit["deferred_scope"]
    assert "meshwell-to-gsim handoff fixture gate are covered" in audit["upstream_gap"]
    assert set(audit["problems"]) == {
        "driven_cpw",
        "eigenmode_resonator",
        "electrostatic_same_layer_capacitor",
    }

    for problem_key, problem in audit["problems"].items():
        manifest = problem["mesh_manifest"]
        index_map = problem["index_map"]
        config = problem["config_generation"]

        assert problem["identity_status"] == "covered_public_fixture"
        assert problem["output_dir"] == problem_key
        assert problem["artifact_paths"] == {
            "config.json": f"{problem_key}/config.json",
            "mesh_manifest.json": f"{problem_key}/mesh_manifest.json",
            "palace_index_map.json": f"{problem_key}/palace_index_map.json",
        }
        assert problem["problem_type"] == config["problem_type"]
        assert config["solver_problem_block"] == problem["problem_type"]
        assert config["domain_material_rows"] == config["domain_material_count"]
        assert config["domain_postprocessing_energy_count"] == 2
        assert manifest["schema_version"] == 1
        assert manifest["entry_count"] > 0
        assert manifest["physical_name_count"] == manifest["entry_count"]
        assert manifest["interface_entry_count"] >= 1
        assert "air___silicon" in manifest["interface_physical_names"]
        assert manifest["entries_without_physical_names"] == []
        assert "dielectric_volume" in manifest["roles"]
        assert index_map["schema_version"] == 1
        assert index_map["entry_count"] > 0
        assert index_map["rows_without_physical_name"] == []
        assert index_map["rows_missing_reverse_lookup"] == []
        assert index_map["rows_missing_attribute_lookup"] == []
        assert "Domains.Postprocessing.Energy" in index_map["sections"]
        assert "mesh_manifest_physical_names" in problem["covered_contracts"]
        assert "palace_index_reverse_lookup" in problem["covered_contracts"]
        assert "meshwell_style_interface_identity" in problem["covered_contracts"]

    driven = audit["problems"]["driven_cpw"]
    assert driven["problem_type"] == "Driven"
    assert driven["index_map"]["port_names"] == ["P1", "P2"]
    assert driven["index_map"]["terminal_names"] == []
    assert driven["config_generation"]["surface_flux_count"] == 4
    assert "port_metadata" in driven["covered_contracts"]

    eigenmode = audit["problems"]["eigenmode_resonator"]
    assert eigenmode["problem_type"] == "Eigenmode"
    assert eigenmode["index_map"]["port_names"] == []
    assert eigenmode["index_map"]["terminal_names"] == []
    assert eigenmode["config_generation"]["surface_flux_count"] == 1

    electrostatic = audit["problems"]["electrostatic_same_layer_capacitor"]
    assert electrostatic["problem_type"] == "Electrostatic"
    assert electrostatic["index_map"]["port_names"] == []
    assert electrostatic["index_map"]["terminal_names"] == ["negative", "positive"]
    assert electrostatic["config_generation"]["terminal_count"] == 2
    assert "terminal_metadata" in electrostatic["covered_contracts"]


def _assert_thin_film_sheet_proxy_interface_evidence(evidence: dict) -> None:
    proxy = evidence["thin_film_sheet_proxy_interface"]
    assert proxy["schema_version"] == 1
    assert proxy["workflow"] == "public-thin-film-sheet-proxy-interface"
    assert proxy["public_default_status"] == "not_public_default"
    assert proxy["caller_record_source"] == "public thin-film sheet proxy fixture only"
    assert proxy["pdk_interface_preset_record_count"] == 0
    assert proxy["output_dir"] == "thin-film-sheet-proxy-interface"
    assert proxy["config_path"] == "thin-film-sheet-proxy-interface/config.json"
    assert proxy["index_map_path"] == ("thin-film-sheet-proxy-interface/palace_index_map.json")

    assert [row["interface_type"] for row in proxy["specs"]] == ["MA", "MS"]
    assert [row["entry_names"] for row in proxy["specs"]] == [
        ["Al___air"],
        ["Al___silicon"],
    ]
    assert {row["preset_source"] for row in proxy["specs"]} == {
        "public thin-film sheet proxy fixture only"
    }
    assert {row["material_name"] for row in proxy["specs"]} == {"AlOx_native_generic"}

    assert [row["Type"] for row in proxy["config_rows"]] == ["MA", "MS"]
    assert all("_MaterialName" not in row for row in proxy["config_rows"])
    assert all(row["Permittivity"] == pytest.approx(10.0) for row in proxy["config_rows"])
    assert all(row["Thickness"] == pytest.approx(0.003) for row in proxy["config_rows"])
    assert all(row["LossTan"] == pytest.approx(0.0) for row in proxy["config_rows"])

    by_source = {row["source_name"]: row for row in proxy["summary_rows"]}
    assert set(by_source) == {"Al___air", "Al___silicon"}
    ma = by_source["Al___air"]
    assert ma["interface_type"] == "MA"
    assert ma["preset_name"] == "public_ma_sheet_proxy_example"
    assert ma["preset_source"] == "public thin-film sheet proxy fixture only"
    assert ma["interface_material_name"] == "AlOx_native_generic"
    assert ma["material_model_source"] == "orpen-sc-pdk tech.material_properties"

    ms = by_source["Al___silicon"]
    assert ms["interface_type"] == "MS"
    assert ms["preset_name"] == "public_ms_sheet_proxy_example"
    assert ms["preset_source"] == "public thin-film sheet proxy fixture only"
    assert ms["interface_material_name"] == "AlOx_native_generic"
    assert ms["material_model_source"] == "orpen-sc-pdk tech.material_properties"


def test_public_thin_film_sheet_proxy_interface_evidence_runs_standalone(
    tmp_path: Path,
) -> None:
    proxy = build_public_thin_film_sheet_proxy_interface_evidence(
        tmp_path / "proxy",
        relative_to=tmp_path,
    )

    assert proxy["output_dir"] == "proxy"
    assert proxy["config_path"] == "proxy/config.json"
    assert proxy["index_map_path"] == "proxy/palace_index_map.json"
    assert (tmp_path / "proxy" / "config.json").is_file()
    assert (tmp_path / "proxy" / "palace_index_map.json").is_file()
    assert [row["interface_type"] for row in proxy["summary_rows"]] == ["MA", "MS"]
    assert [row["source_name"] for row in proxy["summary_rows"]] == [
        "Al___air",
        "Al___silicon",
    ]


def test_public_cad_mesh_identity_handoff_evidence_runs_standalone(
    tmp_path: Path,
) -> None:
    audit = build_public_cad_mesh_identity_handoff_evidence(
        tmp_path / "identity",
        relative_to=tmp_path,
    )

    assert audit["evidence_path"] == ("identity/public_cad_mesh_identity_handoff_evidence.json")
    assert set(audit["problems"]) == {
        "driven_cpw",
        "eigenmode_resonator",
        "electrostatic_same_layer_capacitor",
    }
    assert "magnetostatic_cpw" not in audit["problems"]
    for problem_key, problem in audit["problems"].items():
        assert problem["output_dir"] == f"identity/{problem_key}"
        assert problem["identity_status"] == "covered_public_fixture"
        assert (tmp_path / "identity" / problem_key / "mesh_manifest.json").is_file()
        assert (tmp_path / "identity" / problem_key / "palace_index_map.json").is_file()
        assert (tmp_path / "identity" / problem_key / "config.json").is_file()


def test_public_gsim_boundary_review_coverage_evidence_runs_standalone(
    tmp_path: Path,
) -> None:
    coverage = build_public_gsim_boundary_review_coverage_evidence(
        tmp_path / "coverage",
        relative_to=tmp_path,
    )
    review_rows = load_public_gsim_boundary_review_crosscheck()

    assert coverage["output_dir"] == "coverage"
    assert coverage["evidence_path"] == (
        "coverage/public_gsim_boundary_review_coverage_evidence.json"
    )
    assert (tmp_path / "coverage" / "public_gsim_boundary_review_coverage_evidence.json").is_file()
    assert coverage["coverage_complete"] is True
    assert coverage["missing_from_fixture"] == []
    assert coverage["extra_in_fixture"] == []
    assert coverage["duplicate_fixture_commits"] == []
    assert coverage["fixture_commit_count"] == len(review_rows)
    assert coverage["git_log_commit_count"] == len(review_rows)


def test_public_meshwell_handoff_contract_gate_evidence_runs_standalone(
    tmp_path: Path,
) -> None:
    gate = build_public_meshwell_handoff_contract_gate_evidence(
        tmp_path / "meshwell-gate",
        relative_to=tmp_path,
    )

    assert gate["output_dir"] == "meshwell-gate"
    assert gate["evidence_path"] == (
        "meshwell-gate/public_meshwell_handoff_contract_gate_evidence.json"
    )
    assert (
        tmp_path / "meshwell-gate" / "public_meshwell_handoff_contract_gate_evidence.json"
    ).is_file()
    assert gate["contract_status"] == "formal_contract_and_cross_repo_gate_aligned"
    assert gate["covered_source_count"] == 7
    assert gate["covered_meshwell_backend_equivalence_count"] == 3
    assert gate["covered_gsim_consumer_parser_count"] == 5
    assert gate["covered_cross_repo_consumer_fixture_count"] == 2
    assert gate["pending_count"] == 0
    assert gate["blocking_gaps"] == []


def test_public_interface_preset_promotion_gate_evidence_runs_standalone(
    tmp_path: Path,
) -> None:
    gate = build_public_interface_preset_promotion_gate_evidence(
        tmp_path / "gate",
        relative_to=tmp_path,
    )

    assert gate["output_dir"] == "gate"
    assert gate["evidence_path"] == ("gate/public_interface_preset_promotion_gate_evidence.json")
    assert (tmp_path / "gate" / "public_interface_preset_promotion_gate_evidence.json").is_file()
    assert gate["default_policy_status"] == "not_defined"
    assert gate["pdk_interface_preset_record_count"] == 0
    assert gate["public_default_candidate_ids"] == []


def test_public_palace_smoke_evidence_dry_run_writes_artifacts(tmp_path: Path) -> None:
    evidence = build_public_palace_smoke_evidence(tmp_path, environ={})

    evidence_path = tmp_path / EVIDENCE_FILENAME
    saved = json.loads(evidence_path.read_text())

    assert saved == evidence
    assert evidence["schema_version"] == 1
    assert evidence["workflow"] == "public-palace-smoke-evidence"
    assert evidence["solver"]["enabled"] is False
    assert "ORPEN_RUN_LOCAL_PALACE_SMOKE=1" in evidence["solver"]["skip_reason"]
    _assert_helper_node_inventory(evidence)
    _assert_problem_notebook_crosscheck(evidence)
    _assert_goal_audit(evidence)
    _assert_gsim_boundary_review_crosscheck(evidence)
    _assert_gsim_boundary_review_coverage(evidence)
    _assert_meshwell_handoff_contract_gate(evidence)
    _assert_interface_preset_review_queue(evidence)
    _assert_cad_mesh_identity_handoff_evidence(evidence)
    _assert_interface_preset_promotion_gate_evidence(evidence)
    _assert_thin_film_sheet_proxy_interface_evidence(evidence)
    assert set(evidence["problems"]) == {
        "driven_cpw",
        "eigenmode_resonator",
        "electrostatic_same_layer_capacitor",
        "magnetostatic_cpw",
    }
    sweep_summary = evidence["sweep_summary"]
    assert sweep_summary["sweep_id"] == "public_palace_problem_type_smoke"
    assert sweep_summary["source_path"] == "points.json"
    assert (tmp_path / "points.csv").is_file()
    assert (tmp_path / "run_sweep_array.sbatch").is_file()
    assert (tmp_path / "palace_sweep_handoff_metadata.json").is_file()
    assert (tmp_path / "palace_sweep_handoff_archive_manifest.json").is_file()
    assert sweep_summary["handoff"]["present"] is True
    assert sweep_summary["handoff"]["status"] == "scripted"
    assert sweep_summary["handoff"]["launcher"] == {
        "array": True,
        "dry_run": True,
        "kind": "slurm",
        "submission": "manual",
    }
    assert sweep_summary["handoff"]["profile"] == {
        "launcher": {
            "command_style": "binary",
            "petsc_options": [],
            "srun_args": ["--mpi=pmix"],
        },
        "name": "public-slurm-sweep-dry-run",
        "solver": {"device": "CPU"},
        "source": "caller-supplied public fixture catalog",
    }
    sweep_script = (tmp_path / "run_sweep_array.sbatch").read_text()
    assert 'srun --mpi=pmix "$PALACE_EXECUTABLE" "$CONFIG_PATH"' in sweep_script
    assert sweep_summary["handoff"]["resources"]["array"] == {
        "point_count": 4,
        "max_parallel": 4,
    }
    assert sweep_summary["handoff"]["resources"]["requested"] == {
        "account": "public_alloc",
        "cpus_per_task": 1,
        "gres": None,
        "memory_mb": None,
        "nodes": 1,
        "ntasks_per_node": 1,
        "num_processes": 1,
        "num_threads": 1,
        "partition": "public_cpu",
        "wall_time": "00:10:00",
    }
    assert (
        sweep_summary["handoff"]["resources"]["resolved"]
        == sweep_summary["handoff"]["resources"]["requested"]
    )
    assert sweep_summary["handoff"]["path"] == "palace_sweep_handoff_metadata.json"
    assert sweep_summary["handoff"]["script"]["path"] == "run_sweep_array.sbatch"
    assert sweep_summary["handoff"]["script_present"] is True
    assert sweep_summary["handoff"]["archive"] == {
        "manifest_path": "palace_sweep_handoff_archive_manifest.json"
    }
    assert sweep_summary["handoff"]["archive_present"] is False
    assert sweep_summary["handoff"]["archive_manifest_present"] is True
    assert sweep_summary["handoff"]["metadata"] == {
        "command_style": "binary",
        "point_count": 4,
        "points_csv_path": "points.csv",
        "points_path": "points.json",
        "script_schema_version": 1,
        "workflow": "public-palace-smoke-evidence",
    }
    assert sweep_summary["handoff"]["command"] == {
        "argv": ["sbatch", "run_sweep_array.sbatch"],
        "redacted": True,
    }
    assert sweep_summary["point_count"] == 4
    assert sweep_summary["point_slugs"] == [
        "driven_cpw",
        "eigenmode_resonator",
        "electrostatic_same_layer_capacitor",
        "magnetostatic_cpw",
    ]
    assert sweep_summary["duplicate_point_slugs"] == []
    assert sweep_summary["parse_warnings"] == []
    assert sweep_summary["complete_point_count"] == 4
    assert sweep_summary["runtime_present_count"] == 0
    assert sweep_summary["resource_present_count"] == 4
    assert set(sweep_summary["problem_types"]) == {
        "Driven",
        "Eigenmode",
        "Electrostatic",
        "Magnetostatic",
    }

    sweep_resource_index = evidence["sweep_resource_index"]
    assert sweep_resource_index == {
        "benchmark_jsonl_path": "metadata/records/sweep_benchmark_index.jsonl",
        "point_count": 4,
        "point_records_csv_path": "metadata/records/sweep_point_records.csv",
        "resource_present_count": 4,
        "resource_records_csv_path": "metadata/records/sweep_resource_records.csv",
        "summary_path": "metadata/records/sweep_resource_index.json",
    }
    for path in (
        sweep_resource_index["summary_path"],
        sweep_resource_index["point_records_csv_path"],
        sweep_resource_index["resource_records_csv_path"],
        sweep_resource_index["benchmark_jsonl_path"],
    ):
        assert (tmp_path / path).is_file()
    index_payload = json.loads((tmp_path / sweep_resource_index["summary_path"]).read_text())
    assert index_payload["sweep_id"] == "public_palace_problem_type_smoke"
    assert index_payload["point_count"] == 4
    assert index_payload["resource_present_count"] == 4
    assert index_payload["records"] == {
        "benchmark_jsonl": "metadata/records/sweep_benchmark_index.jsonl",
        "point_records_csv": "metadata/records/sweep_point_records.csv",
        "resource_records_csv": "metadata/records/sweep_resource_records.csv",
    }
    point_records_csv = (tmp_path / sweep_resource_index["point_records_csv_path"]).read_text()
    resource_records_csv = (
        tmp_path / sweep_resource_index["resource_records_csv_path"]
    ).read_text()
    assert "resource_scheduler_job_id" in point_records_csv
    assert "eigenmode_resonator" in resource_records_csv
    benchmark_jsonl_rows = (
        (tmp_path / sweep_resource_index["benchmark_jsonl_path"]).read_text().splitlines()
    )
    assert len(benchmark_jsonl_rows) == 4
    assert {json.loads(row)["point_slug"] for row in benchmark_jsonl_rows} == {
        "driven_cpw",
        "eigenmode_resonator",
        "electrostatic_same_layer_capacitor",
        "magnetostatic_cpw",
    }

    assert [point["point_slug"] for point in sweep_summary["points"]] == [
        "driven_cpw",
        "eigenmode_resonator",
        "electrostatic_same_layer_capacitor",
        "magnetostatic_cpw",
    ]
    point_records = sweep_summary["point_records"]
    assert [record["point_slug"] for record in point_records] == [
        "driven_cpw",
        "eigenmode_resonator",
        "electrostatic_same_layer_capacitor",
        "magnetostatic_cpw",
    ]
    for record in point_records:
        assert record["sweep_id"] == "public_palace_problem_type_smoke"
        assert record["complete"] is True
        assert record["missing_artifact_count"] == 0
        assert record["core_artifact_count"] == 5
        assert record["core_artifact_bytes"] > 0
        assert record["handoff_present"] is True
        assert record["handoff_status"] == "scripted"
        assert record["handoff_profile_name"] == "public-slurm-dry-run"
        assert record["handoff_script_present"] is True
        assert record["handoff_archive_present"] is False
        assert record["handoff_archive_manifest_present"] is True
        assert record["runtime_present"] is False
        assert record["resource_present"] is True
        assert record["resource_status"] == "synthetic"
        assert record["resource_wall_time_seconds"] == pytest.approx(121.0)
        assert record["resource_core_hours"] == pytest.approx(121.0 / 3600)
        assert record["resource_nodes"] == 1
        assert record["resource_num_processes"] == 1
        assert record["resource_num_threads"] == 1
        assert record["resource_global_unknowns"] == 10718029
        assert record["resource_peak_total_hwm_gib"] == pytest.approx(20.8)
        assert record["resource_scheduler_kind"] == "slurm"
        assert record["resource_scheduler_job_id"] == 12345
        assert record["resource_scheduler_job_state"] == "COMPLETED"
        assert record["resource_scheduler_partition"] == "public_cpu"
        if record["parameter_problem_type"] == "Magnetostatic":
            assert record["report_status"] == "skipped"
            assert "unsupported Palace problem type 'Magnetostatic'" in (record["report_message"])
        else:
            assert record["report_status"] == "missing"
        assert record["report_problem_type"] in {
            "Driven",
            "Eigenmode",
            "Electrostatic",
            "Magnetostatic",
        }
        assert record["report_message"]
        assert record["parameter_fixture"]
        assert record["parameter_problem_type"] in {
            "Driven",
            "Eigenmode",
            "Electrostatic",
            "Magnetostatic",
        }

    for problem in evidence["problems"].values():
        output_dir = tmp_path / problem["output_dir"]
        run_summary = problem["run_summary"]

        assert problem["solver_report"]["status"] == "skipped"
        assert output_dir.is_dir()
        config = json.loads((output_dir / "config.json").read_text())
        assert config["Solver"]["Device"] == "CPU"
        assert config["Solver"]["Linear"]
        assert (output_dir / "palace_handoff_metadata.json").is_file()
        assert (output_dir / "palace_handoff_archive_manifest.json").is_file()
        assert (output_dir / "metadata" / "records" / "palace_resource_record.json").is_file()
        assert (output_dir / "metadata" / "records" / "palace_amr_passes.csv").is_file()
        assert (output_dir / "metadata" / "records" / "palace_stage_timing.csv").is_file()
        assert (output_dir / "metadata" / "records" / "palace_stage_memory.csv").is_file()
        assert (output_dir / "metadata" / "scontrol-job-public.txt").is_file()
        assert (output_dir / "logs" / "palace-public-resource.log").is_file()
        assert (output_dir / "run_palace.sbatch").is_file()
        assert run_summary["problem_type"] == problem["problem_type"]
        assert run_summary["config"]["problem_type"] == problem["problem_type"]
        assert run_summary["mesh_manifest"]["present"] is True
        assert run_summary["mesh_manifest"]["entry_count"] > 0
        assert run_summary["index_map"]["present"] is True
        assert run_summary["index_map"]["entry_count"] > 0
        assert run_summary["handoff"]["present"] is True
        assert run_summary["handoff"]["status"] == "scripted"
        assert run_summary["handoff"]["launcher"] == {
            "dry_run": True,
            "kind": "slurm",
            "submission": "manual",
        }
        assert run_summary["handoff"]["profile"] == {
            "launcher": {
                "command_style": "binary",
                "petsc_options": [],
                "srun_args": ["--mpi=pmix"],
            },
            "name": "public-slurm-dry-run",
            "solver": {"device": "CPU"},
            "source": "caller-supplied public fixture catalog",
        }
        script = (output_dir / "run_palace.sbatch").read_text()
        assert 'srun --mpi=pmix "$PALACE_EXECUTABLE" "$PALACE_CONFIG"' in script
        assert run_summary["handoff"]["resources"]["requested"] == {
            "account": "public_alloc",
            "cpus_per_task": 1,
            "gres": None,
            "memory_mb": None,
            "nodes": 1,
            "ntasks_per_node": 1,
            "num_processes": 1,
            "num_threads": 1,
            "partition": "public_cpu",
            "wall_time": "00:10:00",
        }
        assert (
            run_summary["handoff"]["resources"]["resolved"]
            == (run_summary["handoff"]["resources"]["requested"])
        )
        assert (
            run_summary["handoff"]["path"]
            == f"{problem['output_dir']}/palace_handoff_metadata.json"
        )
        assert run_summary["handoff"]["script"]["path"] == "run_palace.sbatch"
        assert run_summary["handoff"]["script_present"] is True
        assert run_summary["handoff"]["archive"] == {
            "manifest_path": "palace_handoff_archive_manifest.json"
        }
        assert run_summary["handoff"]["archive_present"] is False
        assert run_summary["handoff"]["archive_manifest_present"] is True
        assert run_summary["handoff"]["metadata"] == {
            "command_style": "binary",
            "fixture": problem["fixture"],
            "problem_type": problem["problem_type"],
            "script_schema_version": 1,
            "solver_enabled": False,
            "workflow": "public-palace-smoke-evidence",
        }
        assert run_summary["handoff"]["command"] == {
            "argv": ["sbatch", "run_palace.sbatch"],
            "redacted": True,
        }
        assert run_summary["missing_artifacts"] == []
        assert run_summary["runtime"]["present"] is False
        assert run_summary["resource"]["present"] is True
        assert run_summary["resource"]["status"] == "synthetic"
        assert run_summary["resource"]["path"] == (
            f"{problem['output_dir']}/metadata/records/palace_resource_record.json"
        )
        assert run_summary["resource"]["allocation"] == {
            "cores": 1,
            "nodes": 1,
            "num_cpus": 1,
            "num_processes": 1,
            "num_tasks": 1,
            "num_threads": 1,
            "cpus_per_task": 1,
            "requested_memory": "1024M",
            "requested_memory_bytes": 1024 * 1024**2,
        }
        assert run_summary["resource"]["runtime"]["wall_time_seconds"] == pytest.approx(121.0)
        assert run_summary["resource"]["runtime"]["core_hours"] == pytest.approx(121.0 / 3600)
        assert run_summary["resource"]["model_size"]["global_unknowns"] == 10718029
        assert run_summary["resource"]["memory"]["peak_total_hwm_gib"] == pytest.approx(20.8)
        assert run_summary["resource"]["solver"] == {
            "device_configuration": "omp,cpu",
            "libceed_backend": "/cpu/self/xsmm/blocked",
            "memory_configuration": "host-std",
            "palace_git_changeset": "v0.16.1",
            "petsc_version": "3.24.3",
        }
        assert run_summary["resource"]["scheduler"] == {
            "end_time": "2026-05-21T18:26:48",
            "job_id": 12345,
            "job_state": "COMPLETED",
            "kind": "slurm",
            "partition": "public_cpu",
            "run_time": "00:02:01",
            "run_time_seconds": 121,
            "start_time": "2026-05-21T18:24:47",
            "submit_time": "2026-05-21T18:16:44",
            "time_limit": "00:10:00",
            "time_limit_seconds": 600,
        }
        assert run_summary["resource"]["source_count"] == 2
        assert (
            run_summary["resource"]["sources"]["palace_log"]["path"]
            == "logs/palace-public-resource.log"
        )
        assert (
            run_summary["resource"]["sources"]["slurm_scontrol"]["path"]
            == "metadata/scontrol-job-public.txt"
        )
        assert run_summary["resource"]["table_count"] == 3
        assert run_summary["resource"]["tables"]["amr_passes"]["row_count"] == 1
        assert run_summary["resource"]["tables"]["stage_timing"]["row_count"] == 8
        assert run_summary["resource"]["tables"]["stage_memory"]["row_count"] == 8
        assert run_summary["resource"]["tables"]["stage_timing"]["path"] == (
            "metadata/records/palace_stage_timing.csv"
        )
        assert run_summary["resource"]["missing_source_count"] == 1
        assert run_summary["resource"]["metadata"] == {
            "fixture": problem["fixture"],
            "measured": False,
            "problem_type": problem["problem_type"],
            "resource_log_source": "synthetic-public-fixture",
            "workflow": "public-palace-smoke-evidence",
        }
        resource_payload = json.dumps(run_summary["resource"])
        assert "public_palace_fixture" not in resource_payload
        assert "public-node" not in resource_payload

        for artifact_name in (
            "palace.msh",
            "config.json",
            "mesh_manifest.json",
            "palace_index_map.json",
            "palace_material_resolution.json",
        ):
            artifact = run_summary["artifacts"][artifact_name]
            assert artifact["present"] is True
            assert artifact["bytes"] > 0
            assert artifact["sha256"]
            assert (tmp_path / artifact["path"]).is_file()

    driven = evidence["problems"]["driven_cpw"]
    driven_summary = driven["run_summary"]
    driven_config = driven["config_generation"]
    _assert_config_generation_material_provenance(driven)
    driven_lookup = _assert_index_map_lookup_round_trip(driven)
    assert driven_summary["config"]["lumped_port_count"] == 2
    assert driven_config["lumped_port_count"] == 2
    assert driven_config["surface_flux_count"] == 4
    assert driven_config["terminal_count"] == 0
    assert "Boundaries.Postprocessing.SurfaceFlux" in driven_summary["index_map"]["sections"]
    assert driven_summary["index_map"]["port_names"] == ["P1", "P2"]
    assert sorted(
        {
            row["metadata"]["port"]
            for row in driven_lookup
            if row["section"] == "Boundaries.Postprocessing.SurfaceFlux"
        }
    ) == ["P1", "P2"]

    eigenmode = evidence["problems"]["eigenmode_resonator"]
    eigenmode_summary = eigenmode["run_summary"]
    eigenmode_config = eigenmode["config_generation"]
    _assert_config_generation_material_provenance(eigenmode)
    eigenmode_lookup = _assert_index_map_lookup_round_trip(eigenmode)
    assert eigenmode_summary["config"]["problem_type"] == "Eigenmode"
    assert eigenmode_config["domain_postprocessing_energy_count"] == 2
    assert eigenmode_config["surface_flux_count"] == 1
    assert eigenmode_config["terminal_count"] == 0
    assert "Boundaries.Postprocessing.SurfaceFlux" in eigenmode_summary["index_map"]["sections"]
    assert any(
        row["physical_name"] == "absorbing"
        and row["section"] == "Boundaries.Postprocessing.SurfaceFlux"
        for row in eigenmode_lookup
    )

    electrostatic = evidence["problems"]["electrostatic_same_layer_capacitor"]
    electrostatic_summary = electrostatic["run_summary"]
    electrostatic_config = electrostatic["config_generation"]
    _assert_config_generation_material_provenance(electrostatic)
    electrostatic_lookup = _assert_index_map_lookup_round_trip(electrostatic)
    assert electrostatic_summary["config"]["terminal_count"] == 2
    assert electrostatic_config["domain_postprocessing_energy_count"] == 2
    assert electrostatic_config["surface_flux_count"] == 0
    assert electrostatic_config["terminal_count"] == 2
    assert electrostatic_summary["index_map"]["terminal_names"] == [
        "negative",
        "positive",
    ]
    assert sorted(
        row["terminal_name"]
        for row in electrostatic_lookup
        if row["section"] == "Boundaries.Terminal"
    ) == ["negative", "positive"]

    magnetostatic = evidence["problems"]["magnetostatic_cpw"]
    magnetostatic_summary = magnetostatic["run_summary"]
    magnetostatic_config = magnetostatic["config_generation"]
    _assert_config_generation_material_provenance(magnetostatic)
    magnetostatic_lookup = _assert_index_map_lookup_round_trip(magnetostatic)
    assert magnetostatic_summary["config"]["problem_type"] == "Magnetostatic"
    assert magnetostatic_config["surface_current_count"] == 2
    assert magnetostatic_config["surface_current_element_count"] == 2
    assert magnetostatic_config["surface_current_directions"] == [[1.0, 0.0, 0.0]]
    assert magnetostatic_config["surface_current_coordinate_systems"] == ["Cartesian"]
    assert magnetostatic_config["surface_flux_count"] == 2
    assert magnetostatic_config["pmc_count"] == 1
    assert magnetostatic_config["terminal_count"] == 0
    assert "Boundaries.SurfaceCurrent" in magnetostatic_summary["index_map"]["sections"]
    assert "Boundaries.Postprocessing.SurfaceFlux" in magnetostatic_summary["index_map"]["sections"]
    source_rows = [
        row for row in magnetostatic_lookup if row["section"] == "Boundaries.SurfaceCurrent"
    ]
    assert {row["current_source_name"] for row in source_rows} == {
        "return",
        "signal",
    }
    assert sum(row["current_source_name"] == "return" for row in source_rows) == 2
    assert {
        row["extra"].get("current_source_element_count")
        for row in source_rows
        if row["current_source_name"] == "return"
    } == {2}
    assert {
        row["extra"].get("current_source_element_index")
        for row in source_rows
        if row["current_source_name"] == "return"
    } == {1, 2}
    assert {
        tuple(row["extra"]["Direction"])
        if isinstance(row["extra"].get("Direction"), list)
        else row["extra"].get("Direction")
        for row in source_rows
        if row["current_source_name"] == "return"
    } == {"-X", (-1.0, 0.0, 0.0)}
    assert {
        row["extra"].get("CoordinateSystem")
        for row in source_rows
        if row["current_source_name"] == "return"
        and row["extra"].get("CoordinateSystem") is not None
    } == {"Cartesian"}
    assert {
        tuple(row["extra"]["Direction"])
        for row in source_rows
        if row["current_source_name"] == "signal"
    } == {(1.0, 0.0, 0.0)}
    assert {
        row["extra"]["Type"]
        for row in magnetostatic_lookup
        if row["section"] == "Boundaries.Postprocessing.SurfaceFlux"
    } == {"Magnetic"}


def test_public_palace_smoke_evidence_solver_gate_skips_magnetostatic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gsim.palace.base import PalaceSimMixin

    run_local_outputs: list[str] = []

    def fake_run_local(self, **_kwargs):
        output_dir = Path(self.output_dir)
        run_local_outputs.append(output_dir.name)
        return {}

    monkeypatch.setattr(PalaceSimMixin, "run_local", fake_run_local)
    monkeypatch.setattr(
        smoke_evidence,
        "_driven_report_summary",
        lambda _output_dir: {"status": "loaded", "problem_type": "Driven"},
    )
    monkeypatch.setattr(
        smoke_evidence,
        "_eigenmode_report_summary",
        lambda _output_dir: {"status": "loaded", "problem_type": "Eigenmode"},
    )
    monkeypatch.setattr(
        smoke_evidence,
        "_electrostatic_report_summary",
        lambda _output_dir: {"status": "loaded", "problem_type": "Electrostatic"},
    )
    monkeypatch.setattr(
        smoke_evidence,
        "_magnetostatic_report_summary",
        lambda _output_dir: pytest.fail("Magnetostatic report loader should stay deferred"),
    )

    evidence = build_public_palace_smoke_evidence(
        tmp_path,
        environ={
            "ORPEN_RUN_LOCAL_PALACE_SMOKE": "1",
            "PALACE_EXECUTABLE": "/usr/bin/true",
            "PALACE_EXECUTABLE_MODE": "binary",
            "PALACE_NP": "1",
            "PALACE_NT": "1",
        },
    )

    assert evidence["solver"]["enabled"] is True
    assert run_local_outputs == [
        "driven_cpw",
        "eigenmode_resonator",
        "electrostatic_same_layer_capacitor",
    ]

    eigenmode_config = json.loads((tmp_path / "eigenmode_resonator" / "config.json").read_text())
    assert eigenmode_config["Solver"]["Order"] == 1
    assert eigenmode_config["Solver"]["Linear"]["Tol"] == pytest.approx(1e-4)
    assert eigenmode_config["Solver"]["Linear"]["MaxIts"] == 200
    assert eigenmode_config["Solver"]["Eigenmode"] == {
        "N": 1,
        "Target": 6.0,
        "Tol": 1e-3,
    }

    for problem_key in (
        "driven_cpw",
        "eigenmode_resonator",
        "electrostatic_same_layer_capacitor",
    ):
        problem = evidence["problems"][problem_key]
        assert problem["solver_report"]["status"] == "loaded"
        assert problem["run_summary"]["handoff"]["metadata"]["solver_enabled"] is True

    magnetostatic = evidence["problems"]["magnetostatic_cpw"]
    assert magnetostatic["solver_report"] == {
        "status": "skipped",
        "reason": "Magnetostatic local Palace solve deferred by current scope",
    }
    assert magnetostatic["run_summary"]["handoff"]["metadata"]["solver_enabled"] is False
    assert magnetostatic["run_summary"]["resource"]["missing_sources"] == [
        "Magnetostatic local Palace solve deferred by current scope"
    ]


def test_driven_report_summary_uses_sparams_public_keys(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import gsim.palace

    class FakeSParams:
        port_names = ("o1", "o2")
        freq = (4e9, 6e9, 8e9)

        def keys(self) -> list[tuple[str, str]]:
            return [("o1", "o1"), ("o2", "o1")]

        @property
        def data(self):
            raise AssertionError("Use SParams.keys(), not private data storage")

    report = SimpleNamespace(
        sparams=FakeSParams(),
        port_epr=(),
        index_map=(),
        sources=None,
    )
    monkeypatch.setattr(gsim.palace, "load_driven_report", lambda _path: report)

    summary = _driven_report_summary(tmp_path)

    assert summary["status"] == "loaded"
    assert summary["port_names"] == ["o1", "o2"]
    assert summary["frequency_points"] == 3
    assert summary["s_parameter_count"] == 2
