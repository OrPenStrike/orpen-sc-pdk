"""Build the five-point HFSS lead-length/de-embedding research report."""

from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import skrf
from ansys.aedt.core import Hfss
from skrf.network import y2s

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
RUN_ROOT = (
    REPO / "build" / "simulation" / "aedt" / "mtl_transition_hfss_sparameters" / "straight_bend"
)
LEADS = (100, 150, 200, 300, 400)
PORTS = ("o1", "o2", "g_center", "o3", "o4")
SHORT_REDUCED_PORTS = ("o1", "o2", "o3", "o4")
MODE_MAP = {
    "seam:1": "o1",
    "seam:2": "o2",
    "seam:3": "g_center",
    "o3_wave_port": "o3",
    "o4_wave_port": "o4",
}
CASE = "straight_bend_lead{lead}um_ground80um_deembed{lead}um_dzo1pct_terminalmodes_seam5p"
C0_M_PER_S = 299_792_458.0


def case_dir(lead: int) -> Path:
    return RUN_ROOT / CASE.format(lead=lead)


def normalize_touchstone(path: Path) -> skrf.Network:
    network = skrf.Network(str(path))
    names = list(network.port_names or [])
    if sorted(names) != sorted(PORTS):
        raise RuntimeError(f"Unexpected Touchstone ports in {path}: {names!r}")
    order = [names.index(name) for name in PORTS]
    if names != list(PORTS):
        network.s = network.s[:, order, :][:, :, order]
        network.z0 = network.z0[:, order]
        network.port_names = list(PORTS)
        network.write_touchstone(str(path), form="ma", r_ref=50.0, write_z0=False)
        network = skrf.Network(str(path))
    return network


def seconds(value: str) -> int:
    hours, minutes, secs = (int(part) for part in value.split(":"))
    return 3600 * hours + 60 * minutes + secs


def parse_profile(profile: Path, lead: int) -> tuple[dict[str, object], pd.DataFrame]:
    text = profile.read_text(encoding="utf-8", errors="replace").replace("\\'", "'")
    tets = [int(value) for value in re.findall(r"'Tetrahedra', (\d+)", text)]
    matrices = [int(value) for value in re.findall(r"'Matrix size', (\d+)", text)]
    deltas = [float(value) for value in re.findall(r"'Max Mag\. Delta S', ([0-9.eE+-]+)", text)]
    cores = [int(value) for value in re.findall(r"'Cores', (\d+)", text)]
    status = re.findall(r"'Status', '([^']+)'", text)

    def summary_time(label: str) -> int | None:
        match = re.search(
            rf"ProfileItem\('{re.escape(label)}'.*?'Elapsed Time', '([0-9:]+)'",
            text,
        )
        return seconds(match.group(1)) if match else None

    memory = re.search(
        r"ProfileItem\('Adaptive Meshing'.*?'Average memory/process', '([^']+)'"
        r".*?'Max memory/process', '([^']+)'",
        text,
    )
    sweep_memory = re.search(
        r"ProfileItem\('Frequency Sweep'.*?'Total Memory', '([^']+)'",
        text,
    )
    ram_limit = re.search(r"'RAM Limit', (\d+)", text)
    hardware_memory = re.search(r"'Memory', '([^']+)', 3, 'RAM Limit'", text)
    machine = re.search(r"ProfileItem\('Machine'.*?'Name', '([^']+)'", text)

    pass_rows: list[dict[str, object]] = []
    for chunk in re.split(r"\n\s+Name='Adaptive Pass ", text)[1:]:
        number_match = re.match(r"(\d+)'", chunk)
        if not number_match:
            continue
        pass_number = int(number_match.group(1))
        pass_tets = [int(value) for value in re.findall(r"'Tetrahedra', (\d+)", chunk)]
        pass_matrix = [int(value) for value in re.findall(r"'Matrix size', (\d+)", chunk)]
        pass_delta = re.search(r"'Max Mag\. Delta S', ([0-9.eE+-]+)", chunk)
        pass_rows.append(
            {
                "lead_length_um": lead,
                "adaptive_pass": pass_number,
                "tetrahedra": max(pass_tets) if pass_tets else None,
                "matrix_size_dof_proxy": max(pass_matrix) if pass_matrix else None,
                "max_mag_delta_s": float(pass_delta.group(1)) if pass_delta else None,
            }
        )

    timing = json.loads((profile.parents[2] / "solve_timing.json").read_text())
    summary = {
        "lead_length_um": lead,
        "deembed_length_um": lead,
        "analyze_setup_seconds": float(timing["analyze_setup_seconds"]),
        "completed_adaptive_passes": int(timing["completed_adaptive_passes"]),
        "initial_meshing_seconds": summary_time("Initial Meshing"),
        "adaptive_meshing_seconds": summary_time("Adaptive Meshing"),
        "frequency_sweep_seconds": summary_time("Frequency Sweep"),
        "max_tetrahedra": max(tets),
        "max_matrix_size_dof_proxy": max(matrices),
        "final_max_mag_delta_s": deltas[-1],
        "cores": max(cores),
        "ram_limit_percent": int(ram_limit.group(1)) if ram_limit else None,
        "machine_memory": hardware_memory.group(1) if hardware_memory else None,
        "adaptive_average_memory_per_process": memory.group(1) if memory else None,
        "adaptive_max_memory_per_process": memory.group(2) if memory else None,
        "frequency_sweep_total_memory": sweep_memory.group(1) if sweep_memory else None,
        "machine": machine.group(1) if machine else None,
        "status": status[-1] if status else "Unknown",
        "profile_path": str(profile.relative_to(REPO)),
    }
    return summary, pd.DataFrame(pass_rows).drop_duplicates("adaptive_pass")


def short_ground_center(network: skrf.Network) -> skrf.Network:
    """Return the four-port network with ideal V(g_center)=0 termination."""

    keep = [PORTS.index(name) for name in SHORT_REDUCED_PORTS]
    reduced_y = network.y[:, keep, :][:, :, keep]
    reduced_z0 = network.z0[:, keep]
    reduced = skrf.Network(
        frequency=network.frequency.copy(),
        s=y2s(reduced_y, z0=reduced_z0, s_def=network.s_def),
        z0=reduced_z0,
        s_def=network.s_def,
    )
    reduced.port_names = list(SHORT_REDUCED_PORTS)
    if not np.allclose(reduced.y, reduced_y, rtol=1e-9, atol=1e-10):
        raise RuntimeError("Short-circuit Y-matrix reduction did not round-trip")
    return reduced


def plot_matrix(network: skrf.Network, output: Path, *, phase: bool, title: str) -> None:
    count = network.nports
    ports = tuple(network.port_names or [f"o{index + 1}" for index in range(count)])
    fig, axes = plt.subplots(count, count, figsize=(3.6 * count, 2.8 * count), sharex=True)
    frequency = network.f / 1e9
    for destination, row in enumerate(axes):
        for source, axis in enumerate(row):
            values = network.s[:, destination, source]
            if phase:
                axis.plot(frequency, np.unwrap(np.angle(values)) * 180.0 / np.pi, lw=1.1)
                ylabel = "Phase (deg)"
            else:
                axis.plot(frequency, 20.0 * np.log10(np.maximum(np.abs(values), 1e-15)), lw=1.1)
                ylabel = "Magnitude (dB)"
            axis.set_title(f"St({ports[destination]}, {ports[source]})", fontsize=8)
            axis.grid(alpha=0.25)
            if destination == count - 1:
                axis.set_xlabel("Frequency (GHz)")
            if source == 0:
                axis.set_ylabel(ylabel)
    fig.suptitle(title, fontsize=16)
    fig.tight_layout()
    fig.savefig(output, dpi=170)
    plt.close(fig)


def export_point(lead: int) -> dict[str, object]:
    source = case_dir(lead)
    destination = OUT / f"lead_{lead}um"
    destination.mkdir(parents=True, exist_ok=True)
    case_name = CASE.format(lead=lead)
    project = source / f"{case_name}.aedt"
    gds = source / f"{case_name}.gds"
    timing = source / "solve_timing.json"
    metadata = source / "mtl_transition_metadata.json"
    profile = max(source.rglob("*.profile"), key=lambda path: path.stat().st_mtime)
    required = [project, gds, timing, metadata, source / "mtl_transition.s5p", profile]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise RuntimeError(f"Lead {lead} is incomplete: {missing}")

    for path in (project, gds, timing, metadata):
        shutil.copy2(path, destination / path.name)

    cost, adaptive = parse_profile(profile, lead)
    adaptive.to_csv(destination / "adaptive_pass_cost.csv", index=False)

    subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import gdsfactory as gf; "
                "import orpen_sc_pdk; orpen_sc_pdk.activate(); "
                "c=gf.import_gds(sys.argv[1]); f=c.plot(return_fig=True); "
                "f.savefig(sys.argv[2], dpi=180, bbox_inches='tight')"
            ),
            str(gds),
            str(destination / "gdsfactory_layout.png"),
        ],
        check=True,
    )

    app = Hfss(
        project=str(project),
        design=case_name,
        version="2024.2",
        non_graphical=True,
        new_desktop=True,
        close_on_exit=False,
    )
    try:
        app.modeler.refresh_all_ids()
        wave_ports = {boundary.name: boundary for boundary in app.boundaries}
        port_names = ("seam", "o3_wave_port", "o4_wave_port")
        deembed_props = {
            name: (
                bool(wave_ports[name].props.get("DoDeembed", False)),
                wave_ports[name].props.get("DeembedDist"),
            )
            for name in port_names
        }
        for name in port_names:
            wave_ports[name].props["DoDeembed"] = False
            if not wave_ports[name].update():
                raise RuntimeError(f"Could not disable de-embedding for {name}")
        raw_path = destination / "raw_terminal.s5p"
        if not app.export_touchstone(setup="Setup1", sweep="S", output_file=str(raw_path)):
            raise RuntimeError(f"Raw Touchstone export failed for lead {lead}")
        raw = normalize_touchstone(raw_path)

        for name, (enabled, distance) in deembed_props.items():
            wave_ports[name].props["DoDeembed"] = enabled
            if distance is not None:
                wave_ports[name].props["DeembedDist"] = distance
            if not wave_ports[name].update():
                raise RuntimeError(f"Could not restore de-embedding for {name}")
        deembedded_path = destination / "deembedded_terminal.s5p"
        if not app.export_touchstone(setup="Setup1", sweep="S", output_file=str(deembedded_path)):
            raise RuntimeError(f"De-embedded Touchstone export failed for lead {lead}")
        deembedded = normalize_touchstone(deembedded_path)

        original = skrf.Network(str(source / "mtl_transition.s5p"))
        if list(original.port_names or []) != list(PORTS):
            raise RuntimeError(f"Stored de-embedded Touchstone order changed for lead {lead}")
        if np.max(np.abs(deembedded.s - original.s)) > 1e-10:
            raise RuntimeError(f"Re-exported de-embedded S differs for lead {lead}")

        modes = list(MODE_MAP)
        zo_expressions = [f"Zo({mode})" for mode in modes]
        gamma_expressions = [f"Gamma({mode})" for mode in modes]
        zo_data = app.post.get_solution_data(
            expressions=zo_expressions,
            setup_sweep_name="Setup1 : S",
            report_category="Modal Solution Data",
        )
        gamma_data = app.post.get_solution_data(
            expressions=gamma_expressions,
            setup_sweep_name="Setup1 : LastAdaptive",
            report_category="Modal Solution Data",
        )
        if not zo_data or not gamma_data:
            raise RuntimeError(f"Modal Zo/Gamma extraction failed for lead {lead}")

        zo_rows: list[dict[str, object]] = []
        zo_by_mode: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
        for mode, expression in zip(modes, zo_expressions, strict=True):
            frequency, real = zo_data.get_expression_data(expression, "real")
            _, imag = zo_data.get_expression_data(expression, "imag")
            arrays = (np.asarray(frequency), np.asarray(real), np.asarray(imag))
            zo_by_mode[mode] = arrays
            for freq, re_zo, im_zo in zip(*arrays, strict=True):
                zo_rows.append(
                    {
                        "lead_length_um": lead,
                        "physical_mode": mode,
                        "terminal_label": MODE_MAP[mode],
                        "frequency_ghz": freq,
                        "zpi_real_ohm": re_zo,
                        "zpi_imag_ohm": im_zo,
                    }
                )
        pd.DataFrame(zo_rows).to_csv(destination / "modal_zpi_full_sweep.csv", index=False)

        mode_rows: list[dict[str, object]] = []
        for mode, expression in zip(modes, gamma_expressions, strict=True):
            frequency, alpha = gamma_data.get_expression_data(expression, "real")
            _, beta = gamma_data.get_expression_data(expression, "imag")
            zo_freq, zo_real, zo_imag = zo_by_mode[mode]
            for freq, alpha_value, beta_value in zip(frequency, alpha, beta, strict=True):
                omega = 2.0 * math.pi * float(freq) * 1e9
                phase_velocity = omega / float(beta_value) if beta_value else math.nan
                mode_rows.append(
                    {
                        "lead_length_um": lead,
                        "physical_mode": mode,
                        "terminal_label": MODE_MAP[mode],
                        "frequency_ghz": float(freq),
                        "zpi_real_ohm": float(np.interp(freq, zo_freq, zo_real)),
                        "zpi_imag_ohm": float(np.interp(freq, zo_freq, zo_imag)),
                        "alpha_np_per_m": float(alpha_value),
                        "beta_rad_per_m": float(beta_value),
                        "phase_velocity_m_per_s": phase_velocity,
                        "quasi_tem_effective_permittivity": (
                            (C0_M_PER_S / phase_velocity) ** 2
                            if math.isfinite(phase_velocity)
                            else math.nan
                        ),
                    }
                )
        modal = pd.DataFrame(mode_rows)
        modal.to_csv(destination / "modal_characteristics_last_adaptive.csv", index=False)

        selections = [name for name in app.modeler.object_names if name != "Region"]
        if "Region" in app.modeler.object_names:
            app.modeler["Region"].delete()
        app.modeler.fit_all()
        app.post.export_model_picture(
            full_name=str(destination / "hfss_geometry.png"),
            show_axis=True,
            show_grid=True,
            show_ruler=False,
            show_region=False,
            selections=selections,
            orientation="isometric",
            width=1400,
            height=1000,
        )
    finally:
        app.close_project(save=False)
        app.release_desktop(close_projects=True, close_desktop=True)

    plot_matrix(
        raw,
        destination / "raw_s_matrix_magnitude_db.png",
        phase=False,
        title=f"Raw Terminal S matrix — lead {lead} µm",
    )
    plot_matrix(
        raw,
        destination / "raw_s_matrix_phase_deg.png",
        phase=True,
        title=f"Raw Terminal S matrix phase — lead {lead} µm",
    )
    plot_matrix(
        deembedded,
        destination / "deembedded_s_matrix_magnitude_db.png",
        phase=False,
        title=f"De-embedded Terminal S matrix — lead {lead} µm",
    )
    plot_matrix(
        deembedded,
        destination / "deembedded_s_matrix_phase_deg.png",
        phase=True,
        title=f"De-embedded Terminal S matrix phase — lead {lead} µm",
    )
    raw_short = short_ground_center(raw)
    deembedded_short = short_ground_center(deembedded)
    raw_short_path = destination / "raw_g_center_short.s4p"
    deembedded_short_path = destination / "deembedded_g_center_short.s4p"
    raw_short.write_touchstone(str(raw_short_path), form="ma", r_ref=50.0, write_z0=False)
    deembedded_short.write_touchstone(
        str(deembedded_short_path), form="ma", r_ref=50.0, write_z0=False
    )
    for state, network in (("raw", raw_short), ("deembedded", deembedded_short)):
        label = state.capitalize() if state == "raw" else "De-embedded"
        plot_matrix(
            network,
            destination / f"{state}_g_center_short_s_matrix_magnitude_db.png",
            phase=False,
            title=f"{label} Terminal S matrix — g_center short — lead {lead} µm",
        )
        plot_matrix(
            network,
            destination / f"{state}_g_center_short_s_matrix_phase_deg.png",
            phase=True,
            title=f"{label} Terminal S matrix phase — g_center short — lead {lead} µm",
        )

    fig, (axis_zo, axis_beta) = plt.subplots(1, 2, figsize=(13, 5))
    zo_frame = pd.read_csv(destination / "modal_zpi_full_sweep.csv")
    modal_frame = pd.read_csv(destination / "modal_characteristics_last_adaptive.csv")
    for mode in MODE_MAP:
        subset = zo_frame[zo_frame.physical_mode == mode]
        axis_zo.plot(subset.frequency_ghz, subset.zpi_real_ohm, label=mode)
        subset = modal_frame[modal_frame.physical_mode == mode]
        axis_beta.plot(subset.frequency_ghz, subset.beta_rad_per_m, "o-", label=mode)
    axis_zo.set(title="Modal Port Zo (Zpi)", xlabel="Frequency (GHz)", ylabel="Re(Zpi) (Ω)")
    axis_beta.set(
        title="Propagation phase constant — LastAdaptive",
        xlabel="Frequency (GHz)",
        ylabel="β (rad/m)",
    )
    for axis in (axis_zo, axis_beta):
        axis.grid(alpha=0.25)
        axis.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(destination / "modal_characteristics.png", dpi=180)
    plt.close(fig)

    raw_literal = 20.0 * np.log10(np.maximum(np.abs(raw.s[:, 1, 0]), 1e-15))
    de_literal = 20.0 * np.log10(np.maximum(np.abs(deembedded.s[:, 1, 0]), 1e-15))
    report = f"""# Straight + Bend Transition — Lead {lead} µm

## Configuration

- Terminal order: `o1, o2, g_center, o3, o4`
- Lead/de-embed length: {lead} µm
- Finite ground width: 80 µm
- HFSS Driven Terminal; seam has three terminal modes, outer ports one each
- 3–8 GHz Fast sweep, 20,000 points; Max ΔS 0.02; Max ΔZo 1%; 30 cores; RAM limit 45%

## Geometry

![GDSFactory layout](gdsfactory_layout.png)

![HFSS geometry](hfss_geometry.png)

## Complete Terminal Scattering Matrix

Raw magnitude and phase:

![Raw magnitude](raw_s_matrix_magnitude_db.png)

![Raw phase](raw_s_matrix_phase_deg.png)

De-embedded magnitude and phase:

![De-embedded magnitude](deembedded_s_matrix_magnitude_db.png)

![De-embedded phase](deembedded_s_matrix_phase_deg.png)

The literal `St(o2,o1)` mean magnitude is {raw_literal.mean():.3f} dB raw and
{de_literal.mean():.3f} dB after native HFSS wave-port de-embedding. The two
physical trace-through paths are `St(o4,o1)` and `St(o3,o2)`; `St(o2,o1)` is
the seam cross-coupling term, not a through path.

## Ideal-Short Reduction of `g_center`

The explicit center-ground terminal is terminated with `V(g_center)=0` in the
network Y-matrix. The resulting four-port order is `o1, o2, o3, o4`.

Raw short-reduced magnitude and phase:

![Raw short-reduced magnitude](raw_g_center_short_s_matrix_magnitude_db.png)

![Raw short-reduced phase](raw_g_center_short_s_matrix_phase_deg.png)

De-embedded short-reduced magnitude and phase:

![De-embedded short-reduced magnitude](deembedded_g_center_short_s_matrix_magnitude_db.png)

![De-embedded short-reduced phase](deembedded_g_center_short_s_matrix_phase_deg.png)

## Mode Characteristics

![Modal characteristics](modal_characteristics.png)

`modal_zpi_full_sweep.csv` contains HFSS Modal Solution Data / Port Zo (Zpi).
`modal_characteristics_last_adaptive.csv` contains each physical wave-port mode's
Gamma, with α in Np/m and β in rad/m, plus derived phase velocity and quasi-TEM
effective permittivity. The seam mode order is mapped to `o1`, `o2`, and
`g_center` according to the terminal creation order.

## Simulation Cost

- Notebook analyze call: {cost["analyze_setup_seconds"]:.3f} s
- Adaptive passes: {cost["completed_adaptive_passes"]}
- Max tetrahedra: {cost["max_tetrahedra"]:,}
- HFSS max matrix size (DoF proxy): {cost["max_matrix_size_dof_proxy"]:,}
- Final Max Mag ΔS: {cost["final_max_mag_delta_s"]:.6g}
- Adaptive max memory/process: {cost["adaptive_max_memory_per_process"]}
- Frequency-sweep total memory: {cost["frequency_sweep_total_memory"]}

HFSS did not emit a separately labelled total “Degrees of Freedom” field in the
profile; this report therefore preserves the solver-labelled matrix size as the
DoF proxy rather than relabelling it as an exact DoF count.

## Files

- `raw_terminal.s5p`: complete raw complex Terminal network
- `deembedded_terminal.s5p`: complete native HFSS de-embedded Terminal network
- `raw_g_center_short.s4p`: raw four-port network after ideal-short reduction
- `deembedded_g_center_short.s4p`: de-embedded four-port network after ideal-short reduction
- `modal_zpi_full_sweep.csv`: full-frequency modal Zpi
- `modal_characteristics_last_adaptive.csv`: Gamma and derived modal quantities
- `adaptive_pass_cost.csv`: pass-by-pass tetrahedra, matrix size, and ΔS
- `{project.name}`: solved AEDT project
- `{gds.name}`: GDSFactory-exported coupon
"""
    (destination / "report.md").write_text(report, encoding="utf-8")
    return {
        "cost": cost,
        "raw": raw,
        "deembedded": deembedded,
        "raw_short": raw_short,
        "deembedded_short": deembedded_short,
        "modal": modal,
    }


def build_aggregate(points: dict[int, dict[str, object]]) -> None:
    aggregate = OUT / "aggregate"
    aggregate.mkdir(parents=True, exist_ok=True)
    costs = pd.DataFrame([points[lead]["cost"] for lead in LEADS])
    costs.to_csv(aggregate / "simulation_cost.csv", index=False)

    traces = {
        "literal St(o2,o1)": (1, 0),
        "through St(o4,o1)": (4, 0),
        "through St(o3,o2)": (3, 1),
        "center-ground St(g_center,o1)": (2, 0),
    }
    rows: list[dict[str, object]] = []
    for lead in LEADS:
        for state in ("raw", "deembedded"):
            network = points[lead][state]
            for label, (destination, source) in traces.items():
                values = network.s[:, destination, source]
                for frequency, value in zip(network.f / 1e9, values, strict=True):
                    rows.append(
                        {
                            "lead_length_um": lead,
                            "state": state,
                            "trace": label,
                            "frequency_ghz": frequency,
                            "magnitude_db": 20.0 * math.log10(max(abs(value), 1e-15)),
                            "phase_deg": math.degrees(math.atan2(value.imag, value.real)),
                        }
                    )
    trace_frame = pd.DataFrame(rows)
    trace_frame.to_csv(aggregate / "selected_traces.csv", index=False)

    for state in ("raw", "deembedded"):
        fig, axes = plt.subplots(2, 2, figsize=(14, 9), sharex=True)
        for axis, (label, _) in zip(axes.flat, traces.items(), strict=True):
            for lead in LEADS:
                subset = trace_frame[
                    (trace_frame.state == state)
                    & (trace_frame.trace == label)
                    & (trace_frame.lead_length_um == lead)
                ]
                axis.plot(subset.frequency_ghz, subset.magnitude_db, label=f"{lead} µm")
            axis.set(title=label, xlabel="Frequency (GHz)", ylabel="Magnitude (dB)")
            axis.grid(alpha=0.25)
            axis.legend()
        fig.suptitle(f"{state.capitalize()} selected Terminal traces")
        fig.tight_layout(rect=(0, 0, 1, 0.96))
        fig.savefig(aggregate / f"{state}_selected_traces.png", dpi=180)
        plt.close(fig)

    short_traces = {
        "reflection St(o1,o1)": (0, 0),
        "cross-coupling St(o2,o1)": (1, 0),
        "through St(o4,o1)": (3, 0),
        "through St(o3,o2)": (2, 1),
    }
    short_rows: list[dict[str, object]] = []
    for lead in LEADS:
        for state in ("raw_short", "deembedded_short"):
            network = points[lead][state]
            for label, (destination, source) in short_traces.items():
                values = network.s[:, destination, source]
                for frequency, value in zip(network.f / 1e9, values, strict=True):
                    short_rows.append(
                        {
                            "lead_length_um": lead,
                            "state": state,
                            "trace": label,
                            "frequency_ghz": frequency,
                            "magnitude_db": 20.0 * math.log10(max(abs(value), 1e-15)),
                            "phase_deg": math.degrees(math.atan2(value.imag, value.real)),
                        }
                    )
    short_trace_frame = pd.DataFrame(short_rows)
    short_trace_frame.to_csv(aggregate / "g_center_short_selected_traces.csv", index=False)
    for state in ("raw_short", "deembedded_short"):
        fig, axes = plt.subplots(2, 2, figsize=(14, 9), sharex=True)
        for axis, (label, _) in zip(axes.flat, short_traces.items(), strict=True):
            for lead in LEADS:
                subset = short_trace_frame[
                    (short_trace_frame.state == state)
                    & (short_trace_frame.trace == label)
                    & (short_trace_frame.lead_length_um == lead)
                ]
                axis.plot(subset.frequency_ghz, subset.magnitude_db, label=f"{lead} µm")
            axis.set(title=label, xlabel="Frequency (GHz)", ylabel="Magnitude (dB)")
            axis.grid(alpha=0.25)
            axis.legend()
        title = "Raw" if state == "raw_short" else "De-embedded"
        fig.suptitle(f"{title} Terminal traces — ideal-short g_center reduction")
        fig.tight_layout(rect=(0, 0, 1, 0.96))
        fig.savefig(aggregate / f"{state}_g_center_short_selected_traces.png", dpi=180)
        plt.close(fig)

    reference = points[400]["deembedded"]
    stability_rows = []
    for lead in LEADS:
        network = points[lead]["deembedded"]
        difference = network.s - reference.s
        stability_rows.append(
            {
                "lead_length_um": lead,
                "max_abs_complex_s_difference_vs_400um": float(np.max(np.abs(difference))),
                "rms_complex_s_difference_vs_400um": float(
                    np.sqrt(np.mean(np.abs(difference) ** 2))
                ),
            }
        )
    stability = pd.DataFrame(stability_rows)
    stability.to_csv(aggregate / "deembedded_stability_vs_400um.csv", index=False)

    short_reference = points[400]["deembedded_short"]
    short_stability_rows = []
    for lead in LEADS:
        network = points[lead]["deembedded_short"]
        difference = network.s - short_reference.s
        short_stability_rows.append(
            {
                "lead_length_um": lead,
                "max_abs_complex_s_difference_vs_400um": float(np.max(np.abs(difference))),
                "rms_complex_s_difference_vs_400um": float(
                    np.sqrt(np.mean(np.abs(difference) ** 2))
                ),
            }
        )
    short_stability = pd.DataFrame(short_stability_rows)
    short_stability.to_csv(
        aggregate / "deembedded_g_center_short_stability_vs_400um.csv", index=False
    )

    short_consecutive_rows: list[dict[str, object]] = []
    for lower, upper in zip(LEADS[:-1], LEADS[1:], strict=True):
        for label in short_traces:
            lower_trace = short_trace_frame[
                (short_trace_frame.state == "deembedded_short")
                & (short_trace_frame.trace == label)
                & (short_trace_frame.lead_length_um == lower)
            ].magnitude_db.to_numpy()
            upper_trace = short_trace_frame[
                (short_trace_frame.state == "deembedded_short")
                & (short_trace_frame.trace == label)
                & (short_trace_frame.lead_length_um == upper)
            ].magnitude_db.to_numpy()
            short_consecutive_rows.append(
                {
                    "lower_lead_um": lower,
                    "upper_lead_um": upper,
                    "trace": label,
                    "maximum_absolute_magnitude_change_db": float(
                        np.max(np.abs(upper_trace - lower_trace))
                    ),
                    "mean_signed_magnitude_change_db": float(np.mean(upper_trace - lower_trace)),
                }
            )
    short_consecutive = pd.DataFrame(short_consecutive_rows)
    short_consecutive.to_csv(
        aggregate / "consecutive_g_center_short_trace_changes.csv", index=False
    )

    consecutive_rows: list[dict[str, object]] = []
    for lower, upper in zip(LEADS[:-1], LEADS[1:], strict=True):
        for label in traces:
            lower_trace = trace_frame[
                (trace_frame.state == "deembedded")
                & (trace_frame.trace == label)
                & (trace_frame.lead_length_um == lower)
            ].magnitude_db.to_numpy()
            upper_trace = trace_frame[
                (trace_frame.state == "deembedded")
                & (trace_frame.trace == label)
                & (trace_frame.lead_length_um == upper)
            ].magnitude_db.to_numpy()
            consecutive_rows.append(
                {
                    "lower_lead_um": lower,
                    "upper_lead_um": upper,
                    "trace": label,
                    "maximum_absolute_magnitude_change_db": float(
                        np.max(np.abs(upper_trace - lower_trace))
                    ),
                    "mean_signed_magnitude_change_db": float(np.mean(upper_trace - lower_trace)),
                }
            )
    consecutive = pd.DataFrame(consecutive_rows)
    consecutive.to_csv(aggregate / "consecutive_selected_trace_changes.csv", index=False)

    modal_summary = pd.concat([points[lead]["modal"] for lead in LEADS], ignore_index=True)
    modal_summary.to_csv(aggregate / "modal_characteristics_5p5ghz.csv", index=False)
    fig, (axis_zo, axis_beta) = plt.subplots(1, 2, figsize=(12, 4.6))
    for mode in MODE_MAP:
        subset = modal_summary[modal_summary.physical_mode == mode]
        axis_zo.plot(subset.lead_length_um, subset.zpi_real_ohm, "o-", label=mode)
        axis_beta.plot(subset.lead_length_um, subset.beta_rad_per_m, "o-", label=mode)
    axis_zo.set(
        xlabel="Lead length (µm)",
        ylabel="Re(Zpi) at 5.5 GHz (Ω)",
        title="Modal Port Zo stability",
    )
    axis_beta.set(
        xlabel="Lead length (µm)",
        ylabel="β at 5.5 GHz (rad/m)",
        title="Propagation-constant stability",
    )
    for axis in (axis_zo, axis_beta):
        axis.grid(alpha=0.25)
        axis.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(aggregate / "modal_characteristics_vs_lead.png", dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6))
    axes[0].plot(costs.lead_length_um, costs.analyze_setup_seconds / 60.0, "o-")
    axes[0].set(xlabel="Lead length (µm)", ylabel="Analyze time (min)", title="Solve cost")
    axes[1].plot(
        stability.lead_length_um,
        stability.max_abs_complex_s_difference_vs_400um,
        "o-",
        label="5-port maximum",
    )
    axes[1].plot(
        stability.lead_length_um,
        stability.rms_complex_s_difference_vs_400um,
        "o-",
        label="5-port RMS",
    )
    axes[1].plot(
        short_stability.lead_length_um,
        short_stability.max_abs_complex_s_difference_vs_400um,
        "o--",
        label="g_center short maximum",
    )
    axes[1].plot(
        short_stability.lead_length_um,
        short_stability.rms_complex_s_difference_vs_400um,
        "o--",
        label="g_center short RMS",
    )
    axes[1].set(
        xlabel="Lead length (µm)",
        ylabel="Complex |ΔS| vs 400 µm",
        title="De-embedded network stability",
    )
    axes[1].legend()
    for axis in axes:
        axis.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(aggregate / "stability_and_cost.png", dpi=180)
    plt.close(fig)

    selected = stability.sort_values("lead_length_um").to_markdown(index=False, floatfmt=".6g")
    short_selected = short_stability.sort_values("lead_length_um").to_markdown(
        index=False, floatfmt=".6g"
    )
    final_pair = consecutive[
        (consecutive.lower_lead_um == 300) & (consecutive.upper_lead_um == 400)
    ].set_index("trace")
    through_change = final_pair.loc[
        ["through St(o4,o1)", "through St(o3,o2)"],
        "maximum_absolute_magnitude_change_db",
    ].max()
    seam_change = final_pair.loc[
        ["literal St(o2,o1)", "center-ground St(g_center,o1)"],
        "maximum_absolute_magnitude_change_db",
    ].max()
    outer_zo = modal_summary[modal_summary.terminal_label.isin(["o3", "o4"])].zpi_real_ohm
    seam_zo = modal_summary[
        modal_summary.terminal_label.isin(["o1", "o2", "g_center"])
    ].zpi_real_ohm
    network_difference = stability.loc[
        stability.lead_length_um == 300,
        "max_abs_complex_s_difference_vs_400um",
    ].iloc[0]
    short_final_pair = short_consecutive[
        (short_consecutive.lower_lead_um == 300) & (short_consecutive.upper_lead_um == 400)
    ].set_index("trace")
    short_through_change = short_final_pair.loc[
        ["through St(o4,o1)", "through St(o3,o2)"],
        "maximum_absolute_magnitude_change_db",
    ].max()
    short_other_change = short_final_pair.loc[
        ["reflection St(o1,o1)", "cross-coupling St(o2,o1)"],
        "maximum_absolute_magnitude_change_db",
    ].max()
    short_network_difference = short_stability.loc[
        short_stability.lead_length_um == 300,
        "max_abs_complex_s_difference_vs_400um",
    ].iloc[0]
    cost_table = costs[
        [
            "lead_length_um",
            "analyze_setup_seconds",
            "completed_adaptive_passes",
            "max_tetrahedra",
            "max_matrix_size_dof_proxy",
            "adaptive_max_memory_per_process",
            "final_max_mag_delta_s",
        ]
    ].to_markdown(index=False, floatfmt=".6g")
    report = (
        f"""# HFSS Straight + Bend Lead-Length / De-Embedding Sweep

## Technical Summary

This five-point study compares 100, 150, 200, 300, and 400 µm uniform leads
around one straight+bend discontinuity. Every project uses the same W7/S6 CPW,
80 µm finite ground, five Terminal ports, 3–8 GHz Fast sweep with 20,000 points,
Max ΔS 0.02, Maximum ΔZo 1%, and identical conductor/ground mesh policy.

The decision question is not whether a single curve “passes” an invented
tolerance; it is how rapidly the native HFSS de-embedded network approaches the
400 µm reference while geometry and solve cost grow.

## Key Findings

The two physical signal through paths are already magnitude-stable: their
largest 300→400 µm change is only {through_change:.4f} dB. The seam-sensitive
terms are not: `St(o2,o1)` and `St(g_center,o1)` still change by as much as
{seam_change:.3f} dB over the same step. The complete de-embedded 300 µm network
remains {network_difference:.4f}
away from the 400 µm reference in maximum complex |ΔS|.

Modal evidence points to the seam reference plane rather than the outer CPW
ports: outer `o3/o4` Zpi stays within {outer_zo.min():.3f}–{outer_zo.max():.3f} Ω,
while the seam modes span {seam_zo.min():.3f}–{seam_zo.max():.3f} Ω across the
five leads. Therefore this sweep does **not** yet support declaring one lead
length sufficient for the complete five-terminal discontinuity model. It does
support saying that the ordinary signal through paths are stable while the
three-mode seam basis is still lead-dependent.

![Raw selected traces](raw_selected_traces.png)

![De-embedded selected traces](deembedded_selected_traces.png)

The aggregate deliberately shows the literal `St(o2,o1)`, the two physical
through paths `St(o4,o1)` and `St(o3,o2)`, and coupling into the explicit center
ground terminal. All 25 raw and all 25 de-embedded Terminal traces remain in each
parameter report rather than being overplotted here.

![Stability and solve cost](stability_and_cost.png)

![Modal characteristics versus lead](modal_characteristics_vs_lead.png)

### De-embedded complex-network difference relative to 400 µm

{selected}

No numerical accept/reject threshold has been imposed. The table is evidence
for selecting a practical lead length, not an automatic convergence gate.

## Ideal-Short Reduction of `g_center`

The five-port Terminal network is converted to Y, `V(g_center)=0` is imposed,
and the `g_center` row and column are removed. This is an ideal short to the
existing reference ground, not a matched termination. The resulting four-port
order is `o1, o2, o3, o4`; no FEM solve is repeated.

![Raw short-reduced selected traces](raw_short_g_center_short_selected_traces.png)

![De-embedded short-reduced selected traces](deembedded_short_g_center_short_selected_traces.png)

For the 300→400 µm step, the largest physical-through magnitude change after
short reduction is {short_through_change:.4f} dB; the largest selected
reflection/cross-coupling change is {short_other_change:.4f} dB. The complete
short-reduced 300 µm network differs from the 400 µm reference by
{short_network_difference:.4f} in maximum complex |ΔS|.

### De-embedded short-reduced difference relative to 400 µm

{short_selected}

These values remain comparative evidence; no automatic lead-length acceptance
threshold has been introduced.

## Simulation Performance / Benchmarks

{cost_table}

`max_matrix_size_dof_proxy` is the exact HFSS profile label “Max matrix size”.
HFSS did not export a separate total DoF field, so the report does not relabel
this proxy as an exact degree-of-freedom count.

## Scope and Quantity Definitions

- Terminal order: `o1, o2, g_center, o3, o4`.
- Raw S is exported from the solved project after disabling `DoDeembed` on all
  three physical wave ports; this is a post-processing change and does not rerun FEM.
- De-embedded S is exported after restoring each port's native positive lead
  de-embedding distance.
- `St(destination, source)` is Driven Terminal scattering data.
- Modal Port Zo is Zpi because no impedance line is assigned.
- Gamma is extracted from `Setup1 : LastAdaptive`; α is Np/m and β is rad/m.

## De-Embedding Method

In the independent modal basis, a uniform lead gives

`S_raw,ij = exp(-gamma_i * li) * S_DUT,ij * exp(-gamma_j * lj)`.

Moving both reference planes toward the discontinuity therefore removes those
propagation factors. HFSS performs this operation natively using the complex
port propagation constants and lead distances. Because the reported network is
then transformed into a five-terminal basis with three modes at the seam, an
individual Terminal `St(...)` element need not behave like a single uncoupled
scalar mode; magnitude as well as phase can change through modal/terminal basis
mixing.

HFSS documents wave-port de-embedding as a reference-plane post-process and
defines Gamma as α+jβ with α in Np/m and β in rad/m:

- https://ansyshelp.ansys.com/public/Views/Secured/Electronics/v251/en/Subsystems/HFSS/Content/HFSS/DeembeddedSMatricesinHFSS.htm
- https://ansyshelp.ansys.com/public/Views/Secured/Electronics/v251/en/Subsystems/HFSS/Content/HFSS/ComplexPropagationConstant.htm

## Limitations and Robustness

- The longest lead is used only as the comparison reference; it is not declared
  ground truth.
- Gamma is available from the final 5.5 GHz adaptive solution, whereas Modal
  Port Zo is available over the 20,000-point Fast sweep.
- The derived phase velocity/effective permittivity assume quasi-TEM interpretation.
- This report covers the straight+bend topology only. Bend+bend requires its own sweep.

## Recommended Next Step

Use the ideal-short reduction only if the final layout ties `g_center` to the
reference ground over the relevant bandwidth. If that physical contract holds,
select the practical lead from the short-reduced evidence; otherwise replace the
ideal short with the actual ground-connection network before fitting a reusable
S-matrix model.

## Per-Parameter Reports

"""
        + "\n".join(f"- [{lead} µm](../lead_{lead}um/report.md)" for lead in LEADS)
        + "\n"
    )
    (aggregate / "report.md").write_text(report, encoding="utf-8")


def main() -> None:
    missing = [lead for lead in LEADS if not (case_dir(lead) / "solve_timing.json").exists()]
    if missing:
        raise RuntimeError(f"Sweep is not terminal for leads: {missing}")
    points = {lead: export_point(lead) for lead in LEADS}
    build_aggregate(points)
    assert len(list(OUT.glob("lead_*um/report.md"))) == 5
    print(OUT / "aggregate" / "report.md")


if __name__ == "__main__":
    main()
