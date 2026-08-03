# ---
# jupyter:
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
#   language_info:
#     name: python
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.17.3
# ---

# %% [markdown]
# # Two Resonator Bare and Coupled Response from Q2D Diagonal Terms
#
# This notebook is a fast circuit-level pass over the Q2D CPW/MTL data.  It does
# not run AEDT.  It reads diagonal `L` and `C` terms from the Q2D matrix exports,
# builds each lambda/4 resonator from three reusable transmission-line sections,
# extracts weak-probe bare notch frequencies, then compares them with a compact
# two-mode coupled response.

# %%
from __future__ import annotations

import csv
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from orpen_sc_pdk.config import PATH

# %%
# Q2D data source.  This should point at the restored/completed Q2D sweep.
Q2D_RUN_ROOT = PATH.simulation / "aedt" / "q2d_cpw_flip_chip_two_trace_zo_zm" / "2026-07-04-Run01"
Q2D_RAW_MATRIX_CSV = Q2D_RUN_ROOT / "results" / "q2d_raw_matrix_entries.csv"

# Selected CPW specs from the current Zo ~= Zm match candidate.
FLIP_CHIP_GAP_HEIGHT_UM = 7.0
MTL_DIAGONAL_COORDS = {
    "horizontal_offset_um": 6.0,
    "trace_gap_um": 3.0,
    "central_width_um": 20.0,
    "flip_chip_gap_height_um": FLIP_CHIP_GAP_HEIGHT_UM,
}
SINGLE_TRACE_COORDS = {
    "horizontal_offset_um": 30.0,
    "trace_gap_um": 6.0,
    "central_width_um": 3.0,
    "flip_chip_gap_height_um": FLIP_CHIP_GAP_HEIGHT_UM,
}

# Physical section lengths are the design knobs.  Both resonators use:
# single-trace CPW / MTL-diagonal CPW / single-trace CPW.
FILTER_SECTION_LENGTHS_UM = (1500.0, 2000.0, 1500.0)
READOUT_SECTION_LENGTHS_UM = (1400.0, 1900.0, 1400.0)

FREQUENCY_SCAN_HZ = np.linspace(3.0e9, 9.0e9, 24001)
READOUT_LINE_Z0_OHM = 50.0
WEAK_PROBE_LOADED_Q = 12000.0
WEAK_PROBE_NOTCH_DEPTH = 0.015
COUPLING_HZ = 25.0e6
COUPLED_LINEWIDTH_HZ = 5.0e6


# %% [markdown]
# ## Q2D Diagonal Transmission-Line Terms


# %%
@dataclass(frozen=True)
class DiagonalTraceSpec:
    """One CPW spec reduced to diagonal lossless transmission-line terms."""

    name: str
    coords: Mapping[str, float]
    terminal: str
    l_h_per_m: float
    c_f_per_m: float

    @property
    def z0_ohm(self) -> float:
        return math.sqrt(self.l_h_per_m / self.c_f_per_m)

    @property
    def v_m_per_s(self) -> float:
        return 1.0 / math.sqrt(self.l_h_per_m * self.c_f_per_m)

    @property
    def eps_eff(self) -> float:
        return (299_792_458.0 / self.v_m_per_s) ** 2

    def summary(self) -> dict[str, float | str]:
        return {
            "name": self.name,
            "terminal": self.terminal,
            **self.coords,
            "L_H_per_m": self.l_h_per_m,
            "C_F_per_m": self.c_f_per_m,
            "Z0_ohm": self.z0_ohm,
            "v_m_per_s": self.v_m_per_s,
            "eps_eff": self.eps_eff,
        }


def _same_coords(row: Mapping[str, str], coords: Mapping[str, float]) -> bool:
    return all(abs(float(row[key]) - value) < 1e-12 for key, value in coords.items())


def load_diagonal_trace_spec(
    raw_matrix_csv: Path,
    *,
    name: str,
    coords: Mapping[str, float],
    terminal: str = "T1",
) -> DiagonalTraceSpec:
    """Load one diagonal `Lii/Cii` CPW spec from the Q2D long matrix table."""

    if not raw_matrix_csv.is_file():
        raise FileNotFoundError(f"Missing Q2D raw matrix table: {raw_matrix_csv}")

    values: dict[str, float] = {}
    with raw_matrix_csv.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            if not _same_coords(row, coords):
                continue
            if row["row_terminal"] != terminal or row["column_terminal"] != terminal:
                continue
            if row["matrix_source"] == "rl_maxwell" and row["quantity"] == "L":
                values["L"] = float(row["value_si"])
            if row["matrix_source"] == "cg_maxwell" and row["quantity"] == "C":
                values["C"] = float(row["value_si"])

    if set(values) != {"L", "C"}:
        raise ValueError(f"Could not find diagonal L/C for {name}: {coords}")
    if values["L"] <= 0.0 or values["C"] <= 0.0:
        raise ValueError(f"Diagonal L/C must be positive for {name}: {values}")

    return DiagonalTraceSpec(
        name=name,
        coords=dict(coords),
        terminal=terminal,
        l_h_per_m=values["L"],
        c_f_per_m=values["C"],
    )


mtl_diagonal_spec = load_diagonal_trace_spec(
    Q2D_RAW_MATRIX_CSV,
    name="MTL section CPW diagonal terms",
    coords=MTL_DIAGONAL_COORDS,
)
single_trace_spec = load_diagonal_trace_spec(
    Q2D_RAW_MATRIX_CSV,
    name="single trace CPW",
    coords=SINGLE_TRACE_COORDS,
)

trace_spec_summary = [mtl_diagonal_spec.summary(), single_trace_spec.summary()]
trace_spec_summary  # noqa: B018


# %% [markdown]
# ## Part 1: Bare Frequencies with Weak Probe


# %%
@dataclass(frozen=True)
class TLSection:
    """A reusable lossless transmission-line section."""

    name: str
    spec: DiagonalTraceSpec
    length_um: float

    @property
    def length_m(self) -> float:
        return self.length_um * 1e-6

    @property
    def z0_ohm(self) -> float:
        return self.spec.z0_ohm

    @property
    def v_m_per_s(self) -> float:
        return self.spec.v_m_per_s


@dataclass(frozen=True)
class ResonatorConfig:
    """Three-section lambda/4 resonator configuration."""

    name: str
    section_lengths_um: tuple[float, float, float]

    def sections(self) -> tuple[TLSection, TLSection, TLSection]:
        l1, l2, l3 = self.section_lengths_um
        return (
            TLSection("single_trace_input", single_trace_spec, l1),
            TLSection("mtl_diagonal_middle", mtl_diagonal_spec, l2),
            TLSection("single_trace_short_end", single_trace_spec, l3),
        )


filter_resonator = ResonatorConfig("filter_resonator", FILTER_SECTION_LENGTHS_UM)
readout_resonator = ResonatorConfig("readout_resonator", READOUT_SECTION_LENGTHS_UM)


def _section_abcd(freq_hz: np.ndarray, section: TLSection) -> tuple[np.ndarray, ...]:
    beta = 2.0 * np.pi * freq_hz / section.v_m_per_s
    theta = beta * section.length_m
    cos_t = np.cos(theta)
    sin_t = np.sin(theta)
    return (
        cos_t,
        1j * section.z0_ohm * sin_t,
        1j * sin_t / section.z0_ohm,
        cos_t,
    )


def shorted_input_impedance(freq_hz: np.ndarray, sections: Sequence[TLSection]) -> np.ndarray:
    """Input impedance of cascaded TL sections with the far end shorted."""

    if len(sections) != 3:
        raise ValueError("Expected exactly three TL sections")

    a_t = np.ones_like(freq_hz, dtype=np.complex128)
    b_t = np.zeros_like(freq_hz, dtype=np.complex128)
    c_t = np.zeros_like(freq_hz, dtype=np.complex128)
    d_t = np.ones_like(freq_hz, dtype=np.complex128)

    for section in sections:
        a, b, c, d = _section_abcd(freq_hz, section)
        a_t, b_t, c_t, d_t = (
            a_t * a + b_t * c,
            a_t * b + b_t * d,
            c_t * a + d_t * c,
            c_t * b + d_t * d,
        )

    with np.errstate(divide="ignore", invalid="ignore"):
        return b_t / d_t


def quarter_wave_estimate_hz(sections: Sequence[TLSection]) -> float:
    """First-pass lambda/4 estimate from accumulated electrical delay."""

    delay_s = sum(section.length_m / section.v_m_per_s for section in sections)
    if delay_s <= 0.0:
        raise ValueError("Total resonator delay must be positive")
    return 1.0 / (4.0 * delay_s)


def bare_frequency_from_impedance(freq_hz: np.ndarray, sections: Sequence[TLSection]) -> float:
    """Extract the bare lambda/4 frequency from the shorted-line impedance pole."""

    expected = quarter_wave_estimate_hz(sections)
    window = np.abs(freq_hz - expected) <= 0.35 * expected
    if not np.any(window):
        raise ValueError(f"Frequency scan does not cover expected resonance {expected:.6g} Hz")
    impedance = shorted_input_impedance(freq_hz, sections)
    score = np.abs(impedance)
    score = np.where(np.isfinite(score), score, np.nan)
    local_indices = np.flatnonzero(window)
    peak_index = local_indices[int(np.nanargmax(score[window]))]
    return float(freq_hz[peak_index])


def weak_probe_notch_s21(freq_hz: np.ndarray, bare_freq_hz: float) -> np.ndarray:
    """Weak-probe S21 proxy with a shallow notch at the extracted bare frequency."""

    x = 2.0 * WEAK_PROBE_LOADED_Q * (freq_hz - bare_freq_hz) / bare_freq_hz
    return 1.0 - WEAK_PROBE_NOTCH_DEPTH / (1.0 + 1j * x)


def notch_frequency(freq_hz: np.ndarray, s21: np.ndarray) -> float:
    return float(freq_hz[int(np.argmin(np.abs(s21)))])


def build_bare_result(config: ResonatorConfig) -> dict[str, Any]:
    sections = config.sections()
    bare_from_z = bare_frequency_from_impedance(FREQUENCY_SCAN_HZ, sections)
    s21 = weak_probe_notch_s21(FREQUENCY_SCAN_HZ, bare_from_z)
    bare_from_notch = notch_frequency(FREQUENCY_SCAN_HZ, s21)
    assert math.isfinite(bare_from_notch)
    return {
        "name": config.name,
        "section_lengths_um": config.section_lengths_um,
        "total_length_um": sum(config.section_lengths_um),
        "quarter_wave_estimate_GHz": quarter_wave_estimate_hz(sections) / 1e9,
        "bare_frequency_GHz": bare_from_notch / 1e9,
    }


bare_results = [build_bare_result(filter_resonator), build_bare_result(readout_resonator)]
bare_frequency_delta_mhz = (
    bare_results[1]["bare_frequency_GHz"] - bare_results[0]["bare_frequency_GHz"]
) * 1e3
assert len(bare_results) == 2
assert all(row["bare_frequency_GHz"] > 0.0 for row in bare_results)
bare_results, {"readout_minus_filter_MHz": bare_frequency_delta_mhz}  # noqa: B018


# %% [markdown]
# ## Part 2: Coupled Filter/Readout Response


# %%
@dataclass(frozen=True)
class CoupledResonatorModel:
    """Two-mode coupled resonator response from extracted bare frequencies."""

    bare_frequencies_hz: tuple[float, float]
    coupling_hz: float
    linewidth_hz: float

    def __post_init__(self) -> None:
        if len(self.bare_frequencies_hz) != 2:
            raise ValueError("Expected exactly two bare frequencies")
        if self.coupling_hz < 0.0:
            raise ValueError("coupling_hz must be non-negative")
        if self.linewidth_hz <= 0.0:
            raise ValueError("linewidth_hz must be positive")


def coupled_mode_frequencies(model: CoupledResonatorModel) -> np.ndarray:
    f1, f2 = np.asarray(model.bare_frequencies_hz, dtype=float)
    center = 0.5 * (f1 + f2)
    split = math.sqrt((0.5 * (f2 - f1)) ** 2 + model.coupling_hz**2)
    return np.asarray((center - split, center + split))


def coupled_s21_notch(freq_hz: np.ndarray, model: CoupledResonatorModel) -> np.ndarray:
    """Compact coupled-mode S21 proxy with two dressed notch frequencies."""

    s21 = np.ones_like(freq_hz, dtype=np.complex128)
    for mode_hz in coupled_mode_frequencies(model):
        x = 2.0 * (freq_hz - mode_hz) / model.linewidth_hz
        s21 *= 1.0 - 0.35 / (1.0 + 1j * x)
    return s21


def _local_minima(values: np.ndarray) -> np.ndarray:
    if values.size < 3:
        return np.asarray([], dtype=int)
    return np.flatnonzero((values[1:-1] < values[:-2]) & (values[1:-1] < values[2:])) + 1


def find_dip_frequencies(freq_hz: np.ndarray, s21: np.ndarray, *, count: int = 2) -> np.ndarray:
    magnitude = np.abs(s21)
    candidates = _local_minima(magnitude)
    if candidates.size < count:
        candidates = np.argsort(magnitude)[:count]
    else:
        candidates = candidates[np.argsort(magnitude[candidates])[:count]]
    if candidates.size < count:
        raise RuntimeError("Could not find enough S21 dips")
    return np.sort(freq_hz[np.sort(candidates[:count])])


bare_freqs_hz = tuple(row["bare_frequency_GHz"] * 1e9 for row in bare_results)
coupled_model = CoupledResonatorModel(
    bare_frequencies_hz=(float(bare_freqs_hz[0]), float(bare_freqs_hz[1])),
    coupling_hz=COUPLING_HZ,
    linewidth_hz=COUPLED_LINEWIDTH_HZ,
)
span_min = min(bare_freqs_hz) - 250e6
span_max = max(bare_freqs_hz) + 250e6
coupled_freq_hz = np.linspace(span_min, span_max, 20001)
coupled_s21 = coupled_s21_notch(coupled_freq_hz, coupled_model)
coupled_dips_hz = find_dip_frequencies(coupled_freq_hz, coupled_s21)

bare_sorted_hz = np.sort(np.asarray(bare_freqs_hz))
coupled_summary = [
    {
        "mode": index + 1,
        "bare_GHz": float(bare_hz / 1e9),
        "coupled_dip_GHz": float(dip_hz / 1e9),
        "shift_MHz": float((dip_hz - bare_hz) / 1e6),
    }
    for index, (bare_hz, dip_hz) in enumerate(zip(bare_sorted_hz, coupled_dips_hz, strict=True))
]
assert len(coupled_summary) == 2
coupled_summary  # noqa: B018


# %% [markdown]
# ## Coupling Sweep


# %%
def coupled_shift_for(coupling_hz: float) -> dict[str, float]:
    model = CoupledResonatorModel(
        bare_frequencies_hz=(float(bare_freqs_hz[0]), float(bare_freqs_hz[1])),
        coupling_hz=coupling_hz,
        linewidth_hz=COUPLED_LINEWIDTH_HZ,
    )
    modes = coupled_mode_frequencies(model)
    return {
        "coupling_MHz": coupling_hz / 1e6,
        "lower_mode_GHz": float(modes[0] / 1e9),
        "upper_mode_GHz": float(modes[1] / 1e9),
        "lower_shift_MHz": float((modes[0] - bare_sorted_hz[0]) / 1e6),
        "upper_shift_MHz": float((modes[1] - bare_sorted_hz[1]) / 1e6),
        "mode_spacing_MHz": float((modes[1] - modes[0]) / 1e6),
    }


coupling_sweep = [coupled_shift_for(value) for value in (0.0, 5e6, 10e6, 25e6, 50e6)]
coupling_sweep  # noqa: B018


# %% [markdown]
# ## Script Smoke Check

# %%
if __name__ == "__main__":
    print("Trace specs:")
    for row in trace_spec_summary:
        print(row)
    print("Bare frequencies:")
    for row in bare_results:
        print(row)
    print("Bare delta MHz:", bare_frequency_delta_mhz)
    print("Coupled summary:")
    for row in coupled_summary:
        print(row)
    print("Coupling sweep:")
    for row in coupling_sweep:
        print(row)
