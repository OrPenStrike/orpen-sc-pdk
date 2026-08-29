# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.3
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Kosen2024 Xmon — Electrostatic Boundary Alignment Evidence
#
# This analysis-only notebook reads four sealed public runs. It compares the
# ground-referenced Xmon-pad capacitance for two exterior-boundary choices in
# Palace Route B and Q3D. Differences are evidence only; no cross-solver
# agreement threshold or equivalence claim is defined here.

# %% [markdown]
# ## Public Run Controls

# %%
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import matplotlib.pyplot as plt
from IPython.display import display
from scgsim.aedt import resolve_results
from scgsim.palace import inspect_run_trustworthiness
from scipy.constants import e, h

RUN_ROOT = Path.cwd() / ".artifacts"
EVIDENCE_DIR = Path.cwd() / "evidence" / "electrostatic_boundary_alignment"
ORPEN_RUN_SOURCE_COMMIT = "200efdf1887640a5e21e4bf284a44aef5b28223f"
SCGSIM_REVISION = "8f6468408b6553e66d0896833c9076d76cf2d964"
SCGSIM_VERSION = "1.0.0.dev15"

RUNS = (
    {
        "backend": "Palace Route B",
        "boundary": "zero_charge",
        "run_id": "kosen2024_xmon_route_b_es_l309p5_w24p65_g20_vac250_zerocharge_20260829_01",
    },
    {
        "backend": "Palace Route B",
        "boundary": "grounded_enclosure",
        "run_id": "kosen2024_xmon_route_b_es_l309p5_w24p65_g20_vac250_grounded_20260829_01",
    },
    {
        "backend": "Q3D CG-only",
        "boundary": "open_infinity",
        "run_id": "kosen2024_xmon_q3d_l309p5_w24p65_g20_vac250_open_cg_20260829_01",
    },
    {
        "backend": "Q3D CG-only",
        "boundary": "grounded_enclosure",
        "run_id": "kosen2024_xmon_q3d_l309p5_w24p65_g20_vac250_grounded_cg_20260829_02",
    },
)
FAILED_Q3D_ATTEMPT = "kosen2024_xmon_q3d_l309p5_w24p65_g20_vac250_grounded_cg_20260829_01"

# %% [markdown]
# ## Resolve Sealed Runs

# %%
palace_reports = {
    case["boundary"]: inspect_run_trustworthiness(RUN_ROOT / case["run_id"])
    for case in RUNS
    if case["backend"] == "Palace Route B"
}
q3d_results = {
    case["boundary"]: resolve_results(RUN_ROOT / case["run_id"])
    for case in RUNS
    if case["backend"] == "Q3D CG-only"
}

for boundary, report in palace_reports.items():
    display(
        {
            "backend": "Palace Route B",
            "boundary": boundary,
            "completeness": report.completeness,
            "selection": report.selection,
            "failure": report.failure,
        }
    )
for boundary, result in q3d_results.items():
    display({"backend": "Q3D CG-only", "boundary": boundary, **result.convergence})

# %% [markdown]
# ## Ground-Referenced C11 Results

# %%
rows = []
palace_series = {}
for case in RUNS:
    boundary = case["boundary"]
    if case["backend"] == "Palace Route B":
        report = palace_reports[boundary]
        selected = next(
            item
            for item in report.passes
            if item.pass_index == report.selection.selected_pass_index
        )
        c11_ff = selected.capacitance_matrix_f[0][0] * 1e15
        selected_csv = f"{report.selection.selected_path.as_posix()}/terminal-C.csv"
        receipt_output = next(
            item
            for item in report.provenance["returned_receipt"]["output_files"]
            if item["path"] == selected_csv
        )
        palace_series[boundary] = report.passes
        rows.append(
            {
                "backend": case["backend"],
                "exterior_boundary": boundary,
                "run_id": case["run_id"],
                "receipt_status": "failed",
                "result_completeness": report.completeness,
                "selected_evidence": report.selection.selected_path.as_posix(),
                "c11_ff": c11_ff,
                "ec_over_h_mhz": e**2 / (2 * h * c11_ff * 1e-15) / 1e6,
                "native_pass": selected.pass_index + 1,
                "native_measure": "AMR error norm",
                "native_value": selected.error_norm,
                "native_target": report.amr_tolerance,
                "native_converged": False,
                "stop_reason": report.failure.category,
                "runtime_seconds": selected.elapsed_total_s,
                "matrix_sha256": receipt_output["sha256"],
            }
        )
        continue

    result = q3d_results[boundary]
    c_row = next(
        item
        for item in result.physics_results()
        if item["quantity"] == "C" and item["row"] == "xmon_pad" and item["column"] == "xmon_pad"
    )
    if c_row["unit"] != "pF":
        raise ValueError(f"Unexpected Q3D capacitance unit: {c_row['unit']!r}")
    c11_ff = float(c_row["value"]) * 1000.0
    convergence = result.convergence["capacitance"]
    receipt = json.loads(result.receipt_path.read_text())
    rows.append(
        {
            "backend": case["backend"],
            "exterior_boundary": boundary,
            "run_id": case["run_id"],
            "receipt_status": receipt["status"],
            "result_completeness": "complete",
            "selected_evidence": "results/q3d/c_matrix.csv",
            "c11_ff": c11_ff,
            "ec_over_h_mhz": e**2 / (2 * h * c11_ff * 1e-15) / 1e6,
            "native_pass": convergence["final_pass"],
            "native_measure": "matrix delta percent",
            "native_value": convergence["final_matrix_delta_percent"],
            "native_target": convergence["target_percent"],
            "native_converged": convergence["converged"],
            "stop_reason": convergence["stop_reason"],
            "runtime_seconds": receipt["execution_seconds"],
            "matrix_sha256": receipt["outputs"]["results/q3d/c_matrix.csv"],
        }
    )

display(rows)

# %% [markdown]
# ## Comparison and Native Convergence Figures

# %%
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

labels = [
    "Palace\nZero charge",
    "Palace\nGrounded enclosure",
    "Q3D\nOpen / infinity",
    "Q3D\nGrounded enclosure",
]
values = [row["c11_ff"] for row in rows]
fig, ax = plt.subplots(figsize=(9.0, 5.0))
bars = ax.bar(labels, values, color=("#4C78A8", "#72B7B2", "#F58518", "#E45756"))
ax.bar_label(bars, fmt="%.3f fF", padding=3)
ax.set_ylabel("Ground-referenced Xmon C11 (fF)")
ax.set_title("Kosen2024 Xmon electrostatic boundary comparison")
ax.set_ylim(min(values) - 1.0, max(values) + 1.0)
ax.grid(axis="y", alpha=0.25)
fig.tight_layout()
fig.savefig(EVIDENCE_DIR / "comparison.png", dpi=180)
plt.close(fig)

fig, axes = plt.subplots(1, 2, figsize=(12.0, 4.8))
for boundary, passes in palace_series.items():
    axes[0].plot(
        [item.pass_index + 1 for item in passes],
        [item.error_norm for item in passes],
        marker="o",
        label=boundary.replace("_", " "),
    )
axes[0].axhline(0.02, color="black", linestyle=":", label="configured AMR tolerance")
axes[0].set_yscale("log")
axes[0].set_xlabel("Palace AMR pass")
axes[0].set_ylabel("Error norm")
axes[0].set_title("Palace partial-run progression")
axes[0].grid(alpha=0.25)
axes[0].legend()

q3d_rows = [row for row in rows if row["backend"] == "Q3D CG-only"]
q3d_bars = axes[1].bar(
    [row["exterior_boundary"].replace("_", "\n") for row in q3d_rows],
    [row["native_value"] for row in q3d_rows],
    color=("#F58518", "#E45756"),
)
axes[1].bar_label(q3d_bars, fmt="%.6f%%", padding=3)
axes[1].axhline(0.1, color="black", linestyle=":", label="configured target")
axes[1].set_ylabel("Final native matrix delta (%)")
axes[1].set_title("Q3D final adaptive-pass evidence")
axes[1].grid(axis="y", alpha=0.25)
axes[1].legend()
fig.suptitle("Native convergence evidence; no cross-solver agreement gate")
fig.tight_layout()
fig.savefig(EVIDENCE_DIR / "convergence.png", dpi=180)
plt.close(fig)

# %% [markdown]
# ## Public Evidence Packet

# %%
fieldnames = tuple(rows[0])
with (EVIDENCE_DIR / "results.csv").open("w", newline="") as stream:
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)

values_by_case = {(row["backend"], row["exterior_boundary"]): row["c11_ff"] for row in rows}


def difference(lhs: tuple[str, str], rhs: tuple[str, str]) -> dict[str, float]:
    lhs_value = values_by_case[lhs]
    rhs_value = values_by_case[rhs]
    return {
        "absolute_ff": lhs_value - rhs_value,
        "percent_of_rhs": (lhs_value - rhs_value) / rhs_value * 100.0,
    }


failed_receipt = json.loads(
    (RUN_ROOT / FAILED_Q3D_ATTEMPT / "metadata" / "aedt_run_receipt.json").read_text()
)
grounded_q3d_receipt = json.loads(q3d_results["grounded_enclosure"].receipt_path.read_text())
grounded_region = grounded_q3d_receipt["region"]["grounded_region"]
physical_ground_ids = next(
    item["native_object_ids"] for item in grounded_q3d_receipt["nets"] if item["name"] == "ground"
)
enclosure_ids = grounded_region["native_target_net_object_ids"]
run_set = {
    "schema": "orpen.kosen2024.electrostatic-boundary-alignment.v1",
    "semantic_state": "CONVERGING",
    "data_classification": "public",
    "claim": "Measured boundary evidence only; no solver-agreement threshold or equivalence claim.",
    "source": {
        "orpen_run_source_commit": ORPEN_RUN_SOURCE_COMMIT,
        "scgsim_revision": SCGSIM_REVISION,
        "scgsim_version": SCGSIM_VERSION,
    },
    "shared_controls": {
        "component": "kosen2024_flip_chip_xmon_qubit",
        "geometry_um": {"qubit_pad_length": 309.5, "qubit_pad_width": 24.65, "qubit_gap": 20.0},
        "region_padding_um": [250.0, 250.0, 250.0, 250.0, 1000.0, 1000.0],
        "signal": "xmon_pad",
        "physical_ground": "ground",
    },
    "runs": rows,
    "superseded_failed_attempt": {
        "run_id": FAILED_Q3D_ATTEMPT,
        "status": failed_receipt["status"],
        "error": failed_receipt["error"],
        "spec_sha256": failed_receipt["source"]["spec_sha256"],
        "gds_sha256": failed_receipt["source"]["gds_sha256"],
        "reason": (
            "Physical GroundNet name was incorrectly reused for the enclosure; "
            "the artifact remains immutable."
        ),
    },
    "q3d_grounded_region_readback": {
        "spec_sha256": grounded_q3d_receipt["source"]["spec_sha256"],
        "gds_sha256": grounded_q3d_receipt["source"]["gds_sha256"],
        "target_net": grounded_region["target_net"],
        "target_net_origin": grounded_region["target_net_origin"],
        "physical_ground_object_ids": physical_ground_ids,
        "enclosure_object_ids": enclosure_ids,
        "physical_and_enclosure_ids_disjoint": set(physical_ground_ids).isdisjoint(enclosure_ids),
        "thin_conductor_boundaries": [
            item["name"] for item in grounded_region["native_saved_boundaries"]["thin_conductors"]
        ],
        "validate_design_ok": grounded_region["native_design_validation"]["ok"],
    },
    "differences": {
        "palace_grounded_minus_zero_charge": difference(
            ("Palace Route B", "grounded_enclosure"),
            ("Palace Route B", "zero_charge"),
        ),
        "q3d_grounded_minus_open": difference(
            ("Q3D CG-only", "grounded_enclosure"),
            ("Q3D CG-only", "open_infinity"),
        ),
        "open_q3d_minus_zero_charge_palace": difference(
            ("Q3D CG-only", "open_infinity"),
            ("Palace Route B", "zero_charge"),
        ),
        "grounded_q3d_minus_grounded_palace": difference(
            ("Q3D CG-only", "grounded_enclosure"),
            ("Palace Route B", "grounded_enclosure"),
        ),
    },
    "artifacts": {
        name: hashlib.sha256((EVIDENCE_DIR / name).read_bytes()).hexdigest()
        for name in ("results.csv", "comparison.png", "convergence.png")
    },
}
(EVIDENCE_DIR / "run_set.json").write_text(json.dumps(run_set, indent=2) + "\n")
display(run_set)
