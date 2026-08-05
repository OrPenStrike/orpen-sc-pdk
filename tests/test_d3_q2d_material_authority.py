from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from orpen_sc_pdk.simulation.aedt.d3_q2d_material import (
    D3_Q2D_ALLOWED_CONSUMERS,
    MATERIAL_PROFILE_ID,
    SUBSTRATE_AEDT_MATERIAL,
    d3_q2d_material_context,
    d3_q2d_material_profile,
    d3_q2d_policy_identity_from_context,
    sha256_json,
    validate_d3_q2d_material_receipt,
)
from orpen_sc_pdk.simulation.aedt.runtime_bundle import materials as runtime_materials
from scripts import d3_continuous_ground_multidimensional_q2d as continuous_q2d
from scripts.build_d3_same_face_ground_clearance_q2d_package import (
    build_package as build_ground_clearance_package,
)


class _FakeMaterial:
    def __init__(self, name: str) -> None:
        self.name = name

    def update(self) -> bool:
        return True


class _FakeDefinitionManager:
    def GetProjectMaterialNames(self) -> list[str]:
        return [SUBSTRATE_AEDT_MATERIAL]


class _FakeMaterialManager:
    def __init__(self) -> None:
        self.odefinition_manager = _FakeDefinitionManager()
        self.material = _FakeMaterial(SUBSTRATE_AEDT_MATERIAL)

    def exists_material(self, name: str) -> _FakeMaterial | None:
        return self.material if name == SUBSTRATE_AEDT_MATERIAL else None

    def _aedmattolibrary(self, name: str) -> SimpleNamespace:
        assert name == SUBSTRATE_AEDT_MATERIAL
        return SimpleNamespace(
            permittivity=SimpleNamespace(type="simple", value="11.9"),
            permeability=SimpleNamespace(type="simple", value="1"),
            dielectric_loss_tangent=SimpleNamespace(type="simple", value="0"),
            conductivity=SimpleNamespace(type="simple", value="0"),
        )


class _FakeEditor:
    def GetPropertyValue(self, tab: str, object_name: str, property_name: str) -> str:
        assert tab == "Geometry3DAttributeTab"
        assert object_name in {"q2d_die_D0", "q2d_die_D1"}
        assert property_name == "Material"
        return f'"{SUBSTRATE_AEDT_MATERIAL}"'


class _FakeDesktop:
    def GetVersion(self) -> str:
        return "2024.2.0"


def _write_valid_material_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict, dict, dict, dict, Path]:
    run_root = tmp_path / "run"
    result_dir = run_root / "points" / "case" / "q2d"
    result_dir.mkdir(parents=True)
    project_file = run_root / "aedt_project" / "case.aedt"
    project_file.parent.mkdir()
    project_file.write_bytes(b"saved AEDT project evidence")

    material_context = d3_q2d_material_context().model_dump(mode="json")
    app = SimpleNamespace(
        materials=_FakeMaterialManager(),
        modeler=SimpleNamespace(oeditor=_FakeEditor()),
        odesktop=_FakeDesktop(),
        project_file=str(project_file),
        aedt_version_id="ANSYSEM_ROOT242",
    )
    write_attempt = runtime_materials.ensure_aedt_project_materials(
        app,
        material_context,
        result_dir,
    )
    monkeypatch.setattr(runtime_materials.metadata, "version", lambda name: "0.26.2")
    evidence_identity = {
        "case_id": "case",
        "material_context_hash": "a" * 64,
        "cross_section_hash": "b" * 64,
        "layer_stack_hash": "c" * 64,
        "geometry_settings_hash": "d" * 64,
        "recipe_settings_hash": "e" * 64,
        "source_hashes": {
            "aedt_material_context": "a" * 64,
            "q2d_cross_section": "b" * 64,
        },
    }
    receipt = runtime_materials.readback_aedt_project_materials(
        app,
        material_context,
        ["q2d_die_D0", "q2d_die_D1"],
        result_dir,
        evidence_identity,
    )
    return material_context, write_attempt, receipt, evidence_identity, run_root


def _validate_receipt(
    material_context: dict,
    write_attempt: dict,
    receipt: dict,
    evidence_identity: dict,
    run_root: Path,
) -> dict[str, str]:
    return validate_d3_q2d_material_receipt(
        material_context=material_context,
        write_attempt=write_attempt,
        receipt=receipt,
        expected_policy_identity=d3_q2d_policy_identity_from_context(material_context),
        expected_case_id="case",
        expected_material_context_hash=evidence_identity["material_context_hash"],
        expected_cross_section_hash=evidence_identity["cross_section_hash"],
        run_root=run_root,
    )


def test_d3_q2d_material_profile_freezes_accepted_target_policy() -> None:
    profile = d3_q2d_material_profile()
    model = profile["electromagnetic_model"]

    assert profile["material_profile_id"] == MATERIAL_PROFILE_ID
    assert profile["physical_material_id"] == "d3-target-specific-silicon-er11p9"
    assert profile["physical_material_family"] == "silicon"
    assert profile["solver_material_name"] == SUBSTRATE_AEDT_MATERIAL
    assert profile["source_type"] == "custom_project_material"
    assert profile["default_vs_explicit_override"] == "explicit_custom_override"
    assert model["relative_permittivity"] == {
        "value": 11.9,
        "unit": "1",
        "role": "scalar_isotropic_frequency_independent_target_policy",
    }
    assert model["relative_permeability"] == {
        "value": 1.0,
        "unit": "1",
        "role": "explicit_nonmagnetic_modeling_assumption",
    }
    for field in (
        "temperature_K",
        "empirical_condition",
        "crystallographic_orientation",
        "doping_resistivity",
        "empirical_frequency_validity_range",
        "dispersion",
        "anisotropy",
    ):
        assert model[field]["status"] == "NOT_AVAILABLE"
        assert "not represented" in model[field]["reason"]
    for field in ("dielectric_loss_tangent", "conductivity"):
        assert model[field] == {
            "status": "NOT_AVAILABLE",
            "reason": "unconsumed by the lossless LC extraction; not assumed zero",
        }
    assert profile["scientific_claims"] == {
        "measurement": False,
        "ansys_default": False,
        "cryogenic_material_claim": False,
    }
    assert profile["allowed_consumers"] == [
        "d3_q2d",
        "rev10_five_slot_search",
        "stage_2_stage_3_closure",
    ]
    assert profile["allowed_consumers"] == list(D3_Q2D_ALLOWED_CONSUMERS)
    assert continuous_q2d._allowed_consumers_json() == (
        '["d3_q2d","rev10_five_slot_search","stage_2_stage_3_closure"]'
    )
    assert profile["publication_state"] == "diagnostic"
    assert profile["promotion_eligible"] is False


def test_post_save_readback_receipt_validates_complete_hash_bound_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    material_context, write_attempt, receipt, evidence_identity, run_root = (
        _write_valid_material_receipt(tmp_path, monkeypatch)
    )

    identity = _validate_receipt(
        material_context,
        write_attempt,
        receipt,
        evidence_identity,
        run_root,
    )

    assert identity == {
        "material_profile_hash": receipt["material_profile_hash"],
        "material_authority_hash": receipt["material_authority_hash"],
        "material_evidence_snapshot_hash": receipt["material_evidence_snapshot_hash"],
    }
    assert receipt["allowed_consumers"] == list(D3_Q2D_ALLOWED_CONSUMERS)
    assert receipt["material_authority"]["solver_identity"] == {
        "aedt_version": "2024.2",
        "aedt_version_raw": "2024.2.0",
        "pyaedt_version": "0.26.2",
    }
    assert receipt["material_authority"]["properties"]["permittivity"] == {
        "property_type": "simple",
        "normalized_value": 11.9,
        "scientific_authority": True,
    }
    assert (
        receipt["material_authority"]["properties"]["conductivity"]["scientific_authority"] is False
    )


@pytest.mark.parametrize("tamper", ["snapshot", "permittivity", "assignment"])
def test_material_receipt_rejects_missing_or_rehashed_tampering(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tamper: str,
) -> None:
    material_context, write_attempt, receipt, evidence_identity, run_root = (
        _write_valid_material_receipt(tmp_path, monkeypatch)
    )
    tampered = copy.deepcopy(receipt)

    if tamper == "snapshot":
        tampered.pop("material_evidence_snapshot_hash")
    elif tamper == "permittivity":
        authority = tampered["material_authority"]
        authority["properties"]["permittivity"]["normalized_value"] = 11.45
        tampered["material_authority_hash"] = sha256_json(authority)
        tampered["provenance_layers"]["resolved"] = authority
        readback_property = tampered["provenance_layers"]["readback"]["properties"]["permittivity"]
        readback_property["raw_value"] = "11.45"
        readback_property["normalized_value"] = 11.45
        tampered["material_evidence_snapshot_hash"] = sha256_json(
            {
                key: value
                for key, value in tampered.items()
                if key != "material_evidence_snapshot_hash"
            }
        )
    else:
        assignments = tampered["substrate_assignments"]
        assignments[0]["stored_material_name"] = "Silicon"
        tampered["provenance_layers"]["readback"]["substrate_assignments"] = assignments
        tampered["material_evidence_snapshot_hash"] = sha256_json(
            {
                key: value
                for key, value in tampered.items()
                if key != "material_evidence_snapshot_hash"
            }
        )

    with pytest.raises(ValueError):
        _validate_receipt(
            material_context,
            write_attempt,
            tampered,
            evidence_identity,
            run_root,
        )


def test_common_authority_accepts_matching_complete_roles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    common = {
        "material_profile_id": MATERIAL_PROFILE_ID,
        "material_profile_hash": "profile-hash",
        "material_authority_hash": "authority-hash",
        "solver_json": '{"aedt_version":"2024.2","pyaedt_version":"0.26.2"}',
        "common_authority_json": '{"w_nm":3000,"s_nm":3000,"h_nm":8000}',
    }
    single = {**common, "role": "single_reference"}
    pair = {**common, "role": "coupled_pair"}
    validated_roles = []
    monkeypatch.setattr(
        continuous_q2d,
        "_validate_technical_evidence_row",
        lambda row: validated_roles.append(row["role"]),
    )

    continuous_q2d._require_common_authority(single, pair)

    assert validated_roles == ["single_reference", "coupled_pair"]


@pytest.mark.parametrize(
    ("field", "legacy_value"),
    [
        ("material_profile_id", "legacy_11p45"),
        ("material_profile_id", "material_unbound"),
        ("material_profile_hash", "legacy-profile-hash"),
        ("material_authority_hash", "legacy-authority-hash"),
        ("solver_json", '{"aedt_version":"unknown"}'),
        ("common_authority_json", '{"w_nm":7000,"s_nm":6000,"h_nm":8000}'),
    ],
)
def test_common_authority_rejects_legacy_or_mixed_rows(
    field: str,
    legacy_value: str,
) -> None:
    common = {
        "material_profile_id": MATERIAL_PROFILE_ID,
        "material_profile_hash": "profile-hash",
        "material_authority_hash": "authority-hash",
        "solver_json": '{"aedt_version":"2024.2","pyaedt_version":"0.26.2"}',
        "common_authority_json": '{"w_nm":3000,"s_nm":3000,"h_nm":8000}',
    }
    single = {**common, "role": "single_reference"}
    pair = {**common, field: legacy_value, "role": "coupled_pair"}

    with pytest.raises(ValueError, match=field):
        continuous_q2d._require_common_authority(single, pair)


def test_prepare_refuses_old_consumer_database_before_creating_run_root(
    tmp_path: Path,
) -> None:
    empty_database = tmp_path / "empty-v3.sqlite3"
    with continuous_q2d._connect_writer(empty_database):
        pass
    with continuous_q2d._connect_readonly(empty_database) as connection:
        continuous_q2d._require_current_database_authority(connection, empty_database)

    database_path = tmp_path / "old-consumer-v3.sqlite3"
    row = {
        "result_id": "old-consumer-result",
        "request_cache_key": "old-consumer-request",
        "role": "single_reference",
        "input_json": "{}",
        "solver_json": "{}",
        "common_authority_json": "{}",
        "material_profile_id": MATERIAL_PROFILE_ID,
        "material_profile_hash": sha256_json(d3_q2d_material_profile()),
        "material_authority_hash": "authority-hash",
        "material_evidence_snapshot_hash": "snapshot-hash",
        "material_evidence_json": "{}",
        "technical_evidence_complete": 1,
        "evidence_partition": "d3_er11p9_diagnostic_complete",
        "data_class": "project-internal",
        "allowed_consumers_json": '["orpen_candidate_validation"]',
        "publication_state": "diagnostic",
        "promotion_eligible": 0,
        "w_nm": 3000,
        "s_nm": 3000,
        "d_nm": None,
        "h_nm": 8000,
        "c_matrix_json": "[]",
        "l_matrix_json": "[]",
        "convergence_json": "{}",
        "z0_ohm": 50.0,
        "zc1_ohm": None,
        "zc2_ohm": None,
        "zm_ohm": None,
        "source_run_root": str(tmp_path),
        "source_case_id": "old-consumer-case",
        "source_sha256_json": "{}",
        "solver_completed_at": "2026-08-05T00:00:00+00:00",
        "ingested_at": "2026-08-05T00:00:00+00:00",
    }
    with continuous_q2d._connect_writer(database_path) as connection:
        columns = continuous_q2d.DATABASE_COLUMNS
        placeholders = ", ".join("?" for _ in columns)
        connection.execute(
            f"INSERT INTO q2d_material_result ({', '.join(columns)}) VALUES ({placeholders})",
            tuple(row[column] for column in columns),
        )
        connection.commit()
    database_before = database_path.read_bytes()
    run_root = tmp_path / "must-not-exist"

    with pytest.raises(ValueError, match="use a new absent database path"):
        continuous_q2d.prepare_sweep(
            run_root,
            database_path,
            phase_id="authority-gate",
            widths_um=(3.0,),
            gaps_um=(3.0,),
            center_grounds_um=(3.0,),
            heights_um=(8.0,),
        )

    assert not run_root.exists()
    assert database_path.read_bytes() == database_before


@pytest.mark.parametrize("builder_name", ["ground_clearance", "gap_tolerance"])
def test_new_d3_package_builders_emit_only_the_accepted_material_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    builder_name: str,
) -> None:
    if builder_name == "gap_tolerance":
        monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
        from scripts.build_d3_flip_gap_tolerance_q2d_package import (
            build_package as builder,
        )

    else:
        builder = build_ground_clearance_package
    run_root = tmp_path / builder_name
    if builder_name == "gap_tolerance":
        builder(run_root, heights_um=(8.0,))
    else:
        builder(run_root)
    manifest = yaml.safe_load((run_root / "manifest.yaml").read_text(encoding="utf-8"))

    assert manifest["cases"]
    for case in manifest["cases"]:
        recipe = case["recipes"][0]
        assert recipe["material_policy"]["material_profile_id"] == MATERIAL_PROFILE_ID
        assert recipe["material_policy"]["readback_required"] is True

        context = json.loads((run_root / case["aedt_material_context"]).read_text(encoding="utf-8"))
        assert context["material_profile"] == d3_q2d_material_profile()
        assert context["material_profile_hash"] == sha256_json(context["material_profile"])
        assert len(context["compiled_materials"]) == 1
        compiled = context["compiled_materials"][0]
        assert compiled["aedt_material_name"] == SUBSTRATE_AEDT_MATERIAL
        assert compiled["source_physical_material_key"] == "d3-target-specific-silicon-er11p9"
        assert compiled["material_kind"] == "dielectric"
        assert compiled["supported_properties"] == {
            "permittivity": 11.9,
            "permeability": 1.0,
            "dielectric_loss_tangent": None,
            "conductivity": None,
        }

        cross_section = json.loads(
            (run_root / case["q2d_cross_section"]).read_text(encoding="utf-8")
        )
        die_materials = {
            element["material"] for element in cross_section["stack"] if element["kind"] == "die"
        }
        assert die_materials == {SUBSTRATE_AEDT_MATERIAL}
