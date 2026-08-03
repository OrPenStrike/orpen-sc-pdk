# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.17.3
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
# # D3 continuous-ground multidimensional Q2D sweep and length initializer
#
# This notebook owns the local research workflow for extracting continuous-
# ground CPW/MTL cross sections and using consonant candidates
# \(Z_c\approx Z_0,\ v_c\approx v\) to initialize physical lengths.
#
# - \(w,s,d \ge 3\,\mu\mathrm{m}\).
# - Nominal flip-chip height is expected in 7–8 µm.
# - Fabrication-tolerance height samples are 4–9 µm in 0.25 µm steps.
# - \(Z_m=Z_0\) is not a feasibility gate.  Spring2025 Appendix B Eq. (B7)
#   retains \(Z_m/Z_0\) when locating the transfer zero.
# - The stable SQLite file caches only validated completed Q2D points.  AEDT
#   Run folders remain the owner of projects, logs, and raw matrix exports.

# %%
from __future__ import annotations

import json
import math
import sqlite3
import subprocess
import sys
from pathlib import Path

import pandas as pd
from IPython.display import display

REPO_ROOT = Path.cwd().resolve()
if not (REPO_ROOT / "orpen_sc_pdk" / "simulation" / "aedt").is_dir():
    raise RuntimeError("Run this notebook from the orpen_sc_pdk repository root.")

SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from d3_continuous_ground_multidimensional_q2d import (  # noqa: E402
    ingest_sweep,
    plot_sweep,
    prepare_sweep,
)

# %% [markdown]
# ## Explicit run controls
#
# Reusing `DATABASE_PATH` prevents a solved physical point from being recomputed
# in a later Run folder.  Change `RUN_ID` for a new attempt; do not move the
# database inside that Run folder.

# %%
SIMULATION_PURPOSE_ID = "d3_continuous_ground_multidimensional_q2d"
RUN_ID = "2026-07-24-Run01"
PHASE_ID = "broad-root-search-v1"

PURPOSE_ROOT = REPO_ROOT / "build" / "simulation" / "aedt" / SIMULATION_PURPOSE_ID
RUN_ROOT = PURPOSE_ROOT / RUN_ID
DATABASE_PATH = PURPOSE_ROOT / "q2d_point_results_v2.sqlite3"

MINIMUM_FEATURE_UM = 3.0
BROAD_W_UM = (3.0, 6.0, 12.0, 24.0)
BROAD_S_UM = (3.0, 6.0, 12.0, 24.0)
BROAD_D_UM = (3.0, 8.0, 24.0)
BROAD_HEIGHT_UM = (4.0, 7.5, 9.0)
TOLERANCE_HEIGHT_UM = tuple(value / 4 for value in range(16, 37))

assert min(BROAD_W_UM + BROAD_S_UM + BROAD_D_UM) >= MINIMUM_FEATURE_UM
assert TOLERANCE_HEIGHT_UM == tuple(4.0 + 0.25 * index for index in range(21))

# %% [markdown]
# ## Prepare the coarse Run folder
#
# The broad stage has 144 coupled-pair points and 48 deduplicated
# single-reference points.  It samples low, nominal, and high flip-chip height
# before spending solver time on all 21 tolerance heights.

# %%
contract = prepare_sweep(
    RUN_ROOT,
    DATABASE_PATH,
    phase_id=PHASE_ID,
    widths_um=BROAD_W_UM,
    gaps_um=BROAD_S_UM,
    center_grounds_um=BROAD_D_UM,
    heights_um=BROAD_HEIGHT_UM,
)
display(contract)

# %% [markdown]
# ## Native AEDT solve
#
# The generated package is point-local and resumable.  Its `scheduled_cases`
# count already excludes cross-run database hits.  Re-running the same command
# skips completed points in this Run folder.

# %%
SOLVE_COMMAND = [
    "/bin/bash",
    "-lc",
    (
        f"UV_CACHE_DIR=/tmp/uv-cache uv run {RUN_ROOT / 'scripts' / 'run_aedt_native.sh'} "
        "--mode solve --max-workers 7 --num-cores 4 --progress stream"
    ),
]
print(SOLVE_COMMAND[-1])

RUN_SOLVER = False
if RUN_SOLVER:
    subprocess.run(SOLVE_COMMAND, cwd=REPO_ROOT, check=True)

# %% [markdown]
# ## Ingest completed points and export high-dimensional CSV
#
# Ingestion is transactional and single-process.  Incomplete or failed points
# never enter the cache.  The joined CSV retains both pair diagonals so
# \(Z_{c1}/Z_{c2}\) asymmetry remains visible instead of being hidden by their
# mean.

# %%
INGEST_SOLVED_RESULTS = False
if INGEST_SOLVED_RESULTS:
    ingest_summary = ingest_sweep(RUN_ROOT, DATABASE_PATH)
    display(ingest_summary)

RESULT_CSV = RUN_ROOT / "results" / "q2d_impedance_sweep.csv"
ROOT_CELL_CSV = RUN_ROOT / "results" / "q2d_root_cells.csv"
if RESULT_CSV.is_file():
    impedance = pd.read_csv(RESULT_CSV)
    display(
        impedance.sort_values("root_score")[
            [
                "w_um",
                "s_um",
                "d_um",
                "h_um",
                "z0_ohm",
                "zc_ohm",
                "zm_ohm",
                "rc",
                "rm",
                "root_score",
                "zc_asymmetry_relative",
            ]
        ].head(20)
    )
if ROOT_CELL_CSV.is_file() and ROOT_CELL_CSV.stat().st_size:
    root_cells = pd.read_csv(ROOT_CELL_CSV)
    display(root_cells.head(20))

# %% [markdown]
# ## Three-row impedance figures
#
# For the broad stage, each height gets one figure:
#
# - rows: \(Z_0, Z_c, Z_m\);
# - x-axis: \(w\);
# - columns: \(s\);
# - colorbar: \(d\).
#
# Once a local refinement contains all 21 heights, the same function switches
# to height on the x-axis and uses line style for \(d\).

# %%
if RESULT_CSV.is_file() and RESULT_CSV.stat().st_size:
    plot_paths = plot_sweep(RUN_ROOT)
    display(plot_paths)

# %% [markdown]
# ## Refinement contract
#
# After reviewing the signed residuals
# \(r_c=(Z_c-Z_0)/Z_0\) and \(r_m=(Z_m-Z_0)/Z_0\), create the next Run folder
# with a small local \(w,s,d\) neighborhood and `TOLERANCE_HEIGHT_UM`.  The same
# `DATABASE_PATH` reuses every already-completed broad point automatically.
# Nominal candidates are ranked within 7–8 µm; 4–9 µm remains tolerance
# evidence rather than an acceptable nominal-height range.

# %% [markdown]
# ## Spring2025 Appendix-B consonant-line initializer
#
# The 8 µm continuous-ground boundary candidate satisfies \(Z_c\approx Z_0\)
# and \(v_c\approx v\), so Eq. (B7) can retain the observed \(Z_m/Z_0\) rather
# than requiring \(Z_m=Z_0\).  For the symmetric short-tail initializer
# \(\ell_r^s=\ell_p^s\), solve
#
# \[
# A_+(\omega_n)-A_-(\omega_n)=0
# \]
#
# at 4.5 GHz.  The slope of B7 at that zero is response-matched to the
# Appendix-C bridge \(C_n\parallel L_n\); Eq. (C16) then selects \(\ell_c\)
# for \(J/2\pi=5\) MHz.  The resulting lengths are estimator seeds only:
# \(C_{\rm ext}\), loaded-bare shifts, qubit loading, and exact distributed
# response remain downstream checks.

# %%
LENGTH_RUN_ROOT = PURPOSE_ROOT / "2026-07-25-Run03"
LENGTH_RESULTS = LENGTH_RUN_ROOT / "results"
LENGTH_RESULTS.mkdir(parents=True, exist_ok=True)

SELECTED_W_UM = 3.0
SELECTED_S_UM = 3.0
SELECTED_D_UM = 3.0
SELECTED_HEIGHT_UM = 8.0
SLOT_HZ = (5.52e9, 5.76e9, 6.00e9, 6.24e9, 6.48e9)
READOUT_OFFSET_HZ = -2.0e6
FILTER_OFFSET_HZ = 2.0e6
NOTCH_TARGET_HZ = 4.5e9
J_TARGET_HZ = 5.0e6


def matrix_value_si(payload: str, row: str, column: str) -> float:
    """Read one named SI-valued entry from a cached Q2D matrix."""

    matches = [
        float(item["value_si"])
        for item in json.loads(payload)
        if item["row_terminal"] == row and item["column_terminal"] == column
    ]
    if len(matches) != 1:
        raise ValueError(f"expected one {row},{column} matrix entry, found {len(matches)}")
    return matches[0]


with sqlite3.connect(DATABASE_PATH) as connection:
    connection.row_factory = sqlite3.Row
    single = connection.execute(
        """
        SELECT *
        FROM q2d_point_result
        WHERE role = 'single_reference'
          AND w_nm = ? AND s_nm = ? AND d_nm IS NULL AND h_nm = ?
        """,
        (3000, 3000, 8000),
    ).fetchone()
    pair = connection.execute(
        """
        SELECT *
        FROM q2d_point_result
        WHERE role = 'coupled_pair'
          AND w_nm = ? AND s_nm = ? AND d_nm = ? AND h_nm = ?
        """,
        (3000, 3000, 3000, 8000),
    ).fetchone()
if single is None or pair is None:
    raise RuntimeError("The selected 8 µm single/pair Q2D points are missing from the cache.")

single_l = matrix_value_si(single["l_matrix_json"], "T1", "T1")
single_c = matrix_value_si(single["c_matrix_json"], "T1", "T1")
pair_l11 = matrix_value_si(pair["l_matrix_json"], "T1", "T1")
pair_l22 = matrix_value_si(pair["l_matrix_json"], "T2", "T2")
pair_lm = matrix_value_si(pair["l_matrix_json"], "T1", "T2")
pair_c11 = matrix_value_si(pair["c_matrix_json"], "T1", "T1")
pair_c22 = matrix_value_si(pair["c_matrix_json"], "T2", "T2")
pair_cm = -matrix_value_si(pair["c_matrix_json"], "T1", "T2")

Z0_OHM = float(single["z0_ohm"])
ZC_OHM = (float(pair["zc1_ohm"]) + float(pair["zc2_ohm"])) / 2.0
ZM_OHM = float(pair["zm_ohm"])
VELOCITY_M_PER_S = 1.0 / math.sqrt(single_l * single_c)
VC1_M_PER_S = 1.0 / math.sqrt(pair_l11 * pair_c11)
VC2_M_PER_S = 1.0 / math.sqrt(pair_l22 * pair_c22)
RHO = ZM_OHM / Z0_OHM

CONSONANT_MAX_RELATIVE = 0.01
consonant_relative = max(
    abs(ZC_OHM / Z0_OHM - 1.0),
    abs(VC1_M_PER_S / VELOCITY_M_PER_S - 1.0),
    abs(VC2_M_PER_S / VELOCITY_M_PER_S - 1.0),
)
if consonant_relative > CONSONANT_MAX_RELATIVE:
    raise ValueError(f"Selected Q2D point is not consonant within 1%: {consonant_relative:.3%}")


def sinc(value: float) -> float:
    return 1.0 - value**2 / 6.0 if abs(value) < 1.0e-8 else math.sin(value) / value


def sinc_prime(value: float) -> float:
    if abs(value) < 1.0e-6:
        return -value / 3.0 + value**3 / 30.0
    return (value * math.cos(value) - math.sin(value)) / value**2


def b7_bridge_seed(
    *,
    fr_hz: float,
    fp_hz: float,
    coupled_length_m: float,
    rho: float,
) -> dict[str, float]:
    """Return the symmetric-short-tail B7/C16 initializer for one coupled length."""

    wn = 2.0 * math.pi * NOTCH_TARGET_HZ
    wr = 2.0 * math.pi * fr_hz
    wp = 2.0 * math.pi * fp_hz
    x = wn * coupled_length_m / VELOCITY_M_PER_S
    sinc_x = sinc(x)
    cosine = (1.0 - rho**2) / ((1.0 + rho**2) * sinc_x)
    if not -1.0 < cosine < 1.0:
        raise ValueError("B7 has no first real symmetric-short-tail zero for this coupled length.")

    theta = math.acos(cosine)
    notch_path_m = theta * VELOCITY_M_PER_S / wn
    short_m = (notch_path_m - coupled_length_m) / 2.0
    readout_total_m = VELOCITY_M_PER_S / (4.0 * fr_hz)
    filter_total_m = VELOCITY_M_PER_S / (4.0 * fp_hz)
    readout_open_m = readout_total_m - coupled_length_m - short_m
    filter_open_m = filter_total_m - coupled_length_m - short_m
    if min(short_m, readout_open_m, filter_open_m) <= 0.0:
        raise ValueError("B7 target frequencies produce a nonpositive physical section.")

    f_prime = (1.0 + rho**2) * (
        sinc_prime(x) * coupled_length_m / VELOCITY_M_PER_S * math.cos(theta)
        - sinc_x * math.sin(theta) * notch_path_m / VELOCITY_M_PER_S
    )
    denominator = 2.0 * math.cos(math.pi * wn / (2.0 * wr)) * math.cos(math.pi * wn / (2.0 * wp))
    d_im_z21_d_omega = Z0_OHM**2 * wn * coupled_length_m * pair_cm * f_prime / denominator

    cr = readout_total_m / (2.0 * Z0_OHM * VELOCITY_M_PER_S)
    lr = 8.0 * Z0_OHM * readout_total_m / (math.pi**2 * VELOCITY_M_PER_S)
    cp = filter_total_m / (2.0 * Z0_OHM * VELOCITY_M_PER_S)
    lp = 8.0 * Z0_OHM * filter_total_m / (math.pi**2 * VELOCITY_M_PER_S)
    br = wn * cr - 1.0 / (wn * lr)
    bp = wn * cp - 1.0 / (wn * lp)
    cn = -0.5 * d_im_z21_d_omega * br * bp
    if cn <= 0.0:
        raise ValueError("B7 zero slope did not produce a positive response-matched Cn.")
    zn = 1.0 / (wn * cn)

    zr = math.sqrt(lr / cr)
    zp = math.sqrt(lp / cp)
    geometric_omega = math.sqrt(wr * wp)
    j_rad_per_s = (
        math.sqrt(zr * zp)
        / (2.0 * zn)
        * geometric_omega
        * (geometric_omega / wn - wn / geometric_omega)
    )
    zero_residual = (1.0 + rho**2) * sinc_x * math.cos(theta) - (1.0 - rho**2)
    return {
        "fr_hz": fr_hz,
        "fp_hz": fp_hz,
        "lr_open_um": readout_open_m * 1.0e6,
        "lr_short_um": short_m * 1.0e6,
        "lc_um": coupled_length_m * 1.0e6,
        "lp_short_um": short_m * 1.0e6,
        "lp_open_um": filter_open_m * 1.0e6,
        "lr_total_um": readout_total_m * 1.0e6,
        "lp_total_um": filter_total_m * 1.0e6,
        "notch_path_um": notch_path_m * 1.0e6,
        "notch_hz": NOTCH_TARGET_HZ,
        "j_hz": j_rad_per_s / (2.0 * math.pi),
        "cn_fF": cn * 1.0e15,
        "zn_ohm": zn,
        "b7_zero_residual": zero_residual,
    }


def solve_coupled_length(*, slot_hz: float) -> dict[str, float]:
    """Bisect the formula-derived coupled length that reaches the J target."""

    fr_hz = slot_hz + READOUT_OFFSET_HZ
    fp_hz = slot_hz + FILTER_OFFSET_HZ
    lower_m, upper_m = 1.0e-6, 1.0e-3
    lower = b7_bridge_seed(fr_hz=fr_hz, fp_hz=fp_hz, coupled_length_m=lower_m, rho=RHO)
    upper = b7_bridge_seed(fr_hz=fr_hz, fp_hz=fp_hz, coupled_length_m=upper_m, rho=RHO)
    if not lower["j_hz"] < J_TARGET_HZ < upper["j_hz"]:
        raise ValueError("The 1–1000 µm coupled-length bracket does not contain J target.")
    for _ in range(80):
        midpoint_m = (lower_m + upper_m) / 2.0
        midpoint = b7_bridge_seed(
            fr_hz=fr_hz,
            fp_hz=fp_hz,
            coupled_length_m=midpoint_m,
            rho=RHO,
        )
        if midpoint["j_hz"] < J_TARGET_HZ:
            lower_m = midpoint_m
        else:
            upper_m = midpoint_m
    result = b7_bridge_seed(
        fr_hz=fr_hz,
        fp_hz=fp_hz,
        coupled_length_m=(lower_m + upper_m) / 2.0,
        rho=RHO,
    )
    result["slot_hz"] = slot_hz
    return result


# Exact check: generalized B7 slope matching must reduce to Spring Eq. (C17)
# for equal resonator frequencies and homogeneous-medium rho=1.
homogeneous = b7_bridge_seed(
    fr_hz=6.0e9,
    fp_hz=6.0e9,
    coupled_length_m=160.0e-6,
    rho=1.0,
)
omega_bar = 2.0 * math.pi * 6.0e9
omega_n = 2.0 * math.pi * NOTCH_TARGET_HZ
capacitance_per_m = 1.0 / (Z0_OHM * VELOCITY_M_PER_S)
spring_c17_j_hz = (
    omega_bar
    * math.pi**2
    / 32.0
    * (omega_bar / omega_n - omega_n / omega_bar) ** 3
    / math.cos(math.pi * omega_n / (2.0 * omega_bar)) ** 2
    * (pair_cm / capacitance_per_m)
    * math.sin(omega_n * 160.0e-6 / VELOCITY_M_PER_S)
    / (2.0 * math.pi)
)
assert math.isclose(homogeneous["j_hz"], spring_c17_j_hz, rel_tol=1.0e-12)

length_specs = pd.DataFrame(solve_coupled_length(slot_hz=slot) for slot in SLOT_HZ)
assert length_specs["b7_zero_residual"].abs().max() < 1.0e-12

LENGTH_SPEC_CSV = LENGTH_RESULTS / "spring2025_b7_consonant_length_seeds.csv"
LENGTH_SPEC_JSON = LENGTH_RESULTS / "spring2025_b7_consonant_length_seeds.json"
length_specs.to_csv(LENGTH_SPEC_CSV, index=False)
LENGTH_SPEC_JSON.write_text(
    json.dumps(
        {
            "schema_version": "d3-spring2025-b7-consonant-length-seeds.v1",
            "status": "estimator_only_not_distributed_validated",
            "q2d_cache_keys": {
                "single_reference": single["cache_key"],
                "coupled_pair": pair["cache_key"],
            },
            "q2d_sources": {
                role: {
                    "source_run_root": row["source_run_root"],
                    "source_case_id": row["source_case_id"],
                    "source_sha256": json.loads(row["source_sha256_json"]),
                    "solver_completed_at": row["solver_completed_at"],
                }
                for role, row in (
                    ("single_reference", single),
                    ("coupled_pair", pair),
                )
            },
            "cross_section_um": {
                "w": SELECTED_W_UM,
                "s": SELECTED_S_UM,
                "d": SELECTED_D_UM,
                "flip_chip_height": SELECTED_HEIGHT_UM,
            },
            "q2d_readback": {
                "z0_ohm": Z0_OHM,
                "zc_ohm": ZC_OHM,
                "zm_ohm": ZM_OHM,
                "single_velocity_m_per_s": VELOCITY_M_PER_S,
                "coupled_diagonal_line_velocities_m_per_s": [
                    VC1_M_PER_S,
                    VC2_M_PER_S,
                ],
                "consonant_max_relative": consonant_relative,
                "lm_over_lc": pair_lm / ((pair_l11 + pair_l22) / 2.0),
                "cm_over_cc": pair_cm / ((pair_c11 + pair_c22) / 2.0 - pair_cm),
            },
            "targets": {
                "notch_hz": NOTCH_TARGET_HZ,
                "j_hz": J_TARGET_HZ,
                "readout_offset_hz": READOUT_OFFSET_HZ,
                "filter_offset_hz": FILTER_OFFSET_HZ,
            },
            "formula_scope": (
                "Spring2025 Appendix B Eq. B7 zero and slope, response-matched "
                "bridge LC, Appendix C Eq. C16; symmetric short-tail initializer"
            ),
            "rows": length_specs.to_dict(orient="records"),
        },
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)

display(
    pd.DataFrame(
        {
            "quantity": (
                "Z0",
                "Zc mean",
                "Zm",
                "v",
                "max consonant residual",
                "lm/lc",
                "cm/cc",
            ),
            "value": (
                Z0_OHM,
                ZC_OHM,
                ZM_OHM,
                VELOCITY_M_PER_S,
                consonant_relative,
                pair_lm / ((pair_l11 + pair_l22) / 2.0),
                pair_cm / ((pair_c11 + pair_c22) / 2.0 - pair_cm),
            ),
        }
    )
)
display(
    length_specs[
        [
            "slot_hz",
            "lr_open_um",
            "lr_short_um",
            "lc_um",
            "lp_short_um",
            "lp_open_um",
            "notch_path_um",
            "j_hz",
        ]
    ]
)
