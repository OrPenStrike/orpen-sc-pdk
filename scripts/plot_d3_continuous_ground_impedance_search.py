"""Summarize solved 8 um continuous-ground D3 impedance screens."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt


def _cases(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload.get("cases")
    if payload.get("artifact_status") != "complete" or not isinstance(cases, list):
        raise ValueError(f"Incomplete Q2D artifact: {path}")
    return cases


def _matching_single(pair: dict, singles: list[dict]) -> dict:
    parameters = pair["parameters"]
    scale = parameters.get("lateral_scale")
    if scale is not None:
        matches = [
            case
            for case in singles
            if case["parameters"].get("lateral_scale") == scale
        ]
    else:
        matches = [
            case
            for case in singles
            if case["parameters"]["trace_width_um"] == parameters["trace_width_um"]
            and case["parameters"]["trace_gap_um"] == parameters["trace_gap_um"]
        ]
    if len(matches) != 1:
        raise ValueError("Each pair case must resolve exactly one single reference.")
    return matches[0]


def _rows(label: str, artifact_dir: Path) -> list[dict[str, float | str]]:
    pairs = _cases(artifact_dir / "coupled_pair_maxwell_lc.json")
    singles = _cases(artifact_dir / "single_reference_maxwell_lc.json")
    rows = []
    for pair in pairs:
        parameters = pair["parameters"]
        single = _matching_single(pair, singles)
        z0 = float(single["derived"]["self_impedance_ohm"]["T1"])
        zc = sum(float(value) for value in pair["derived"]["self_impedance_ohm"].values()) / 2
        zm = float(pair["derived"]["mutual_impedance_ohm"])
        mean = (z0 + zc + zm) / 3
        rows.append(
            {
                "screen": label,
                "lateral_scale": parameters.get("lateral_scale") or "",
                "trace_width_um": float(parameters["trace_width_um"]),
                "trace_gap_um": float(parameters["trace_gap_um"]),
                "inter_trace_ground_width_um": float(
                    parameters["inter_trace_ground_width_um"]
                ),
                "z0_ohm": z0,
                "zc_ohm": zc,
                "zm_ohm": zm,
                "max_pairwise_relative_mismatch": max(
                    abs(z0 - zc), abs(z0 - zm), abs(zc - zm)
                )
                / mean,
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--screen",
        action="append",
        nargs=2,
        metavar=("LABEL", "ARTIFACT_DIR"),
        required=True,
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    rows = [
        row
        for label, artifact_dir in args.screen
        for row in _rows(label, Path(artifact_dir))
    ]
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    csv_path = output / "continuous_ground_impedance_search.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    d_rows = sorted(
        (row for row in rows if row["screen"] == "center-ground-only"),
        key=lambda row: float(row["inter_trace_ground_width_um"]),
    )
    scale_rows = sorted(
        (row for row in rows if row["screen"].startswith("lateral-scale")),
        key=lambda row: float(row["lateral_scale"]),
    )
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.6), constrained_layout=True)
    for ax, subset, x_key, x_label, title in (
        (
            axes[0],
            d_rows,
            "inter_trace_ground_width_um",
            "Inter-trace ground d (µm)",
            "Fixed w=5 µm, s=7.5 µm",
        ),
        (
            axes[1],
            scale_rows,
            "lateral_scale",
            "Uniform lateral scale α",
            "(w, s, d) = α(5, 7.5, 5.5) µm",
        ),
    ):
        x = [float(row[x_key]) for row in subset]
        for key, label, marker in (
            ("z0_ohm", "Z₀", "o"),
            ("zc_ohm", "Zc", "s"),
            ("zm_ohm", "Zm", "^"),
        ):
            ax.plot(x, [float(row[key]) for row in subset], marker=marker, label=label)
        ax.set_title(title)
        ax.set_xlabel(x_label)
        ax.set_ylabel("Extracted impedance (Ω)")
        ax.grid(alpha=0.25)
        ax.legend()
    fig.suptitle("D3 8 µm continuous D1-ground Q2D impedance search", fontweight="bold")
    fig.savefig(output / "continuous_ground_impedance_search.png", dpi=220)
    fig.savefig(output / "continuous_ground_impedance_search.svg")
    plt.close(fig)
    print(output)


if __name__ == "__main__":
    main()
