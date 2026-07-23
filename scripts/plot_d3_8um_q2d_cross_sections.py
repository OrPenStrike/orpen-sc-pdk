"""Draw dimensioned D3 8 um single-trace and MTL Q2D cross-sections."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

GROUND = "#d8aa32"
TRACE = "#d95f02"
SUBSTRATE = "#a9d6e5"
AIR = "#eef7fa"
INK = "#263238"


def _case(path: Path, role: str) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload.get("cases")
    if payload.get("artifact_status") != "complete" or not isinstance(cases, list):
        raise ValueError(f"Incomplete Q2D artifact: {path}")
    if len(cases) != 1 or cases[0].get("case_role") != role:
        raise ValueError(f"Expected one {role} case in {path}")
    return cases[0]


def _hdim(ax, x0: float, x1: float, y: float, label: str) -> None:
    ax.annotate("", (x1, y), (x0, y), arrowprops={"arrowstyle": "<->", "color": INK})
    ax.text((x0 + x1) / 2, y + 0.22, label, ha="center", va="bottom", color=INK)


def _vdim(ax, x: float, y0: float, y1: float, label: str) -> None:
    ax.annotate("", (x, y1), (x, y0), arrowprops={"arrowstyle": "<->", "color": INK})
    ax.text(x + 1.1, (y0 + y1) / 2, label, ha="left", va="center", color=INK)


def _base_figure(parameters: dict, title: str):
    fig, (ax, table_ax) = plt.subplots(
        1,
        2,
        figsize=(15, 7.8),
        gridspec_kw={"width_ratios": [4.0, 2.0]},
        constrained_layout=True,
    )
    fig.suptitle(title, fontsize=19, fontweight="bold", color=INK)
    ax.set_xlim(-48, 48)
    ax.set_ylim(-3.2, 11.2)
    ax.set_facecolor(AIR)
    ax.add_patch(Rectangle((-48, -2), 96, 2, facecolor=SUBSTRATE, edgecolor=INK))
    ax.add_patch(Rectangle((-48, 8), 96, 2, facecolor=SUBSTRATE, edgecolor=INK))
    ax.text(-45.5, -1, "D0 silicon substrate\n(truncated)", va="center", color=INK)
    ax.text(-45.5, 9, "D1 silicon substrate retained\n(truncated)", va="center", color=INK)

    clearance = float(parameters["upper_ground_clearance_width_um"])
    metal = float(parameters["metal_thickness_um"])
    if clearance == 0.0:
        ax.add_patch(Rectangle((-48, 8 - metal), 96, metal, color=GROUND, ec=INK))
    else:
        ax.add_patch(
            Rectangle(
                (-48, 8 - metal),
                48 - clearance / 2,
                metal,
                color=GROUND,
                ec=INK,
            )
        )
        ax.add_patch(
            Rectangle(
                (clearance / 2, 8 - metal),
                48 - clearance / 2,
                metal,
                color=GROUND,
                ec=INK,
            )
        )
        _hdim(
            ax,
            -clearance / 2,
            clearance / 2,
            6.65,
            f"clearance = {clearance:g} µm",
        )
    _vdim(ax, 43, 0, float(parameters["flip_chip_gap_height_um"]), "h = 8 µm")
    ax.text(
        26,
        8.55,
        ("D1 bottom Ground Plane (continuous)" if clearance == 0.0 else "D1 bottom Ground Plane"),
        ha="center",
        color=INK,
    )
    ax.text(
        -47,
        -2.8,
        "Local interface view: substrate thickness and outer-ground extent "
        "are intentionally truncated.",
        fontsize=9.5,
        color=INK,
    )
    ax.set_xlabel("Lateral position (µm)")
    ax.set_ylabel("Vertical stack (schematic)")
    ax.set_xticks(range(-40, 41, 10))
    ax.set_yticks([])
    ax.spines[["top", "right", "left"]].set_visible(False)
    table_ax.axis("off")
    return fig, ax, table_ax


def _dimension_table(table_ax, parameters: dict, *, include_d: bool, impedance_rows):
    rows = [
        ("Trace width, w", f"{parameters['trace_width_um']:g} µm"),
        ("CPW gap, s", f"{parameters['trace_gap_um']:g} µm"),
    ]
    if include_d:
        rows.append(
            (
                "Inter-trace ground, d",
                f"{parameters['inter_trace_ground_width_um']:g} µm",
            )
        )
    rows.extend(
        [
            ("Flip-chip height, h", f"{parameters['flip_chip_gap_height_um']:g} µm"),
            (
                "Upper-ground excavation",
                (
                    "None (continuous)"
                    if parameters["upper_ground_clearance_width_um"] == 0.0
                    else f"{parameters['upper_ground_clearance_width_um']:g} µm"
                ),
            ),
            ("Metal thickness, t", f"{parameters['metal_thickness_um']:g} µm"),
            ("Outer ground per side", f"{parameters['ground_width_um']:g} µm"),
            *impedance_rows,
        ]
    )
    table = table_ax.table(
        cellText=rows,
        colLabels=("Parameter", "Value"),
        cellLoc="left",
        colLoc="left",
        loc="center",
        colWidths=(0.58, 0.42),
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.75)
    for (row, _), cell in table.get_celld().items():
        cell.set_edgecolor("#c7d0d5")
        if row == 0:
            cell.set_facecolor(INK)
            cell.set_text_props(color="white", fontweight="bold")


def _draw_single(case: dict, output: Path) -> None:
    p = case["parameters"]
    derived = case["derived"]
    fig, ax, table_ax = _base_figure(p, "D3 8 µm Flip-Chip CPW — Single Trace (Z₀ extraction)")
    w = float(p["trace_width_um"])
    s = float(p["trace_gap_um"])
    metal = float(p["metal_thickness_um"])
    edge = w / 2 + s
    ax.add_patch(Rectangle((-48, 0), 48 - edge, metal, color=GROUND, ec=INK))
    ax.add_patch(Rectangle((edge, 0), 48 - edge, metal, color=GROUND, ec=INK))
    ax.add_patch(Rectangle((-w / 2, 0), w, metal, color=TRACE, ec=INK))
    ax.text(0, -0.35, "T1", ha="center", va="top", fontweight="bold", color=TRACE)
    ax.text(-28, 0.55, "D0 Ground", ha="center", color=INK)
    ax.text(28, 0.55, "D0 Ground", ha="center", color=INK)
    _hdim(ax, -w / 2, w / 2, 1.1, f"w = {w:g} µm")
    _hdim(ax, w / 2, edge, 1.9, f"s = {s:g} µm")
    ax.annotate(
        f"metal t = {metal:g} µm",
        xy=(0, metal),
        xytext=(10, 3.1),
        arrowprops={"arrowstyle": "->", "color": INK},
        color=INK,
    )
    _dimension_table(
        table_ax,
        p,
        include_d=False,
        impedance_rows=[
            ("Extracted Z₀", f"{derived['self_impedance_ohm']['T1']:.3f} Ω"),
        ],
    )
    for suffix in ("png", "svg"):
        fig.savefig(output / f"single_trace_cross_section.{suffix}", dpi=220)
    plt.close(fig)


def _draw_mtl(case: dict, output: Path) -> None:
    p = case["parameters"]
    derived = case["derived"]
    fig, ax, table_ax = _base_figure(p, "D3 8 µm Flip-Chip CPW — MTL Section (Zc / Zm extraction)")
    w = float(p["trace_width_um"])
    s = float(p["trace_gap_um"])
    d = float(p["inter_trace_ground_width_um"])
    metal = float(p["metal_thickness_um"])
    half_d = d / 2
    t2_left = half_d + s
    t2_right = t2_left + w
    t1_right = -t2_left
    t1_left = t1_right - w
    outer_edge = t2_right + s
    for x, width in ((-48, 48 - outer_edge), (-half_d, d), (outer_edge, 48 - outer_edge)):
        ax.add_patch(Rectangle((x, 0), width, metal, color=GROUND, ec=INK))
    ax.add_patch(Rectangle((t1_left, 0), w, metal, color=TRACE, ec=INK))
    ax.add_patch(Rectangle((t2_left, 0), w, metal, color=TRACE, ec=INK))
    ax.text((t1_left + t1_right) / 2, -0.35, "T1", ha="center", va="top", color=TRACE)
    ax.text((t2_left + t2_right) / 2, -0.35, "T2", ha="center", va="top", color=TRACE)
    ax.text(0, 0.55, "Central Ground", ha="center", color=INK)
    _hdim(ax, t1_left, t1_right, 1.05, f"w = {w:g} µm")
    _hdim(ax, -half_d, half_d, 1.75, f"d = {d:g} µm")
    _hdim(ax, t1_right, -half_d, 2.45, f"s = {s:g} µm")
    ax.text(0, 3.15, "All four CPW gaps use the same s", ha="center", color=INK)
    _dimension_table(
        table_ax,
        p,
        include_d=True,
        impedance_rows=[
            ("Extracted Zc, T1", f"{derived['self_impedance_ohm']['T1']:.3f} Ω"),
            ("Extracted Zc, T2", f"{derived['self_impedance_ohm']['T2']:.3f} Ω"),
            ("Extracted Zm", f"{derived['mutual_impedance_ohm']:.3f} Ω"),
        ],
    )
    for suffix in ("png", "svg"):
        fig.savefig(output / f"mtl_section_cross_section.{suffix}", dpi=220)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    single = _case(args.artifact_dir / "single_reference_maxwell_lc.json", "single_reference")
    pair = _case(args.artifact_dir / "coupled_pair_maxwell_lc.json", "coupled_pair")
    if single["parameters"]["flip_chip_gap_height_um"] != 8.0:
        raise ValueError("Single-trace artifact is not the requested 8 um case.")
    if pair["parameters"]["flip_chip_gap_height_um"] != 8.0:
        raise ValueError("MTL artifact is not the requested 8 um case.")
    _draw_single(single, output)
    _draw_mtl(pair, output)
    expected = [
        output / f"{stem}.{suffix}"
        for stem in ("single_trace_cross_section", "mtl_section_cross_section")
        for suffix in ("png", "svg")
    ]
    if not all(path.is_file() and path.stat().st_size > 0 for path in expected):
        raise RuntimeError("Cross-section rendering did not produce all expected files.")
    print(output)


if __name__ == "__main__":
    main()
