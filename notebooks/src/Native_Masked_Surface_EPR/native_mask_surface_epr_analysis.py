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
# # Native Masked Surface EPR Analysis

# %%
from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

import pandas as pd
import plotly.express as px
from IPython.display import display

# %%
RUN_ROOT: Path = Path("/path/to/hpc_handoff_package")
SOURCE_INDEX = 1
WRITE_HTML = True
WRITE_STATIC_IMAGE = False
STATIC_IMAGE_FORMAT = "png"

# %% [markdown]
# ## Convergence Plots

# %%
run_root = RUN_ROOT.expanduser().resolve()
metadata_path = run_root / "metadata" / "native_mask_postprocessing.json"
results_root = run_root / "results" / "palace"

if not metadata_path.is_file():
    raise FileNotFoundError(f"Missing native Mask metadata: {metadata_path}")
if not results_root.is_dir():
    raise FileNotFoundError(f"Missing Palace results folder: {results_root}")

metadata = json.loads(metadata_path.read_text())
groups = metadata.get("groups", [])
if not groups:
    raise ValueError(f"Native Mask metadata has no groups: {metadata_path}")

groups_by_key = defaultdict(list)
for group in groups:
    key = (str(group["interface_type"]), int(group["mask_margin_nm"]))
    groups_by_key[key].extend(int(row_index) for row_index in group["row_indices"])

result_dirs = []
for candidate in sorted(results_root.glob("iteration*")):
    match = re.fullmatch(r"iteration(\d+)", candidate.name)
    if match and (candidate / "surface-mask-Q.csv").is_file():
        pass_index = int(match.group(1))
        result_dirs.append((pass_index, f"Pass {pass_index}", candidate))

root_surface_mask = results_root / "surface-mask-Q.csv"
if root_surface_mask.is_file():
    latest_index = max((row[0] for row in result_dirs), default=0) + 1
    result_dirs.append((latest_index, "Latest root", results_root))

if not result_dirs:
    raise FileNotFoundError(f"No surface-mask-Q.csv files found under: {results_root}")

rows = []
for pass_index, label, result_dir in result_dirs:
    surface_mask_path = result_dir / "surface-mask-Q.csv"
    with surface_mask_path.open(newline="") as handle:
        records = [
            {key.strip(): value.strip() for key, value in row.items()}
            for row in csv.DictReader(handle)
        ]
    source_row = next(
        (row for row in records if int(round(float(row["i"]))) == SOURCE_INDEX),
        None,
    )
    if source_row is None:
        raise ValueError(f"Missing source index {SOURCE_INDEX} in {surface_mask_path}")

    for (interface_type, margin_nm), row_indices in groups_by_key.items():
        value = 0.0
        for row_index in row_indices:
            column = f"p_surf_mask[{row_index}]"
            if column not in source_row:
                raise KeyError(f"Missing column {column!r} in {surface_mask_path}")
            value += float(source_row[column])
        margin_label = f"{margin_nm} nm" if margin_nm < 1000 else "1 um"
        rows.append(
            {
                "pass_index": pass_index,
                "label": label,
                "source_index": SOURCE_INDEX,
                "interface_type": interface_type,
                "mask_margin_nm": margin_nm,
                "mask_margin_label": margin_label,
                "series_label": f"{margin_label}, {interface_type}",
                "p_surf_mask_sum": value,
                "p_surf_mask_sum_micro": value * 1e6,
            }
        )

history = pd.DataFrame(rows).sort_values(["pass_index", "interface_type", "mask_margin_nm"])
label_order = [label for _, label, _ in result_dirs]
visible_history = history.copy()
visible_history["label"] = pd.Categorical(
    visible_history["label"],
    categories=label_order,
    ordered=True,
)

route = metadata.get("surface_epr_route")
route_label = f"SGB Route {route} " if route else ""
fig = px.line(
    visible_history,
    x="label",
    y="p_surf_mask_sum",
    color="series_label",
    markers=True,
    log_y=True,
    title=f"{route_label}Native Masked Surface EPR Convergence - All Interfaces",
)
fig.update_layout(
    xaxis_title="label",
    yaxis_title="p_surf_mask_sum (log scale)",
    legend_title_text="",
)

written_files = []
if WRITE_HTML:
    html_path = run_root / "native_mask_surface_epr_convergence.html"
    fig.write_html(html_path)
    written_files.append(html_path)
if WRITE_STATIC_IMAGE:
    image_path = run_root / f"native_mask_surface_epr_convergence.{STATIC_IMAGE_FORMAT}"
    fig.write_image(image_path)
    written_files.append(image_path)

fig.show()
display(
    {
        "run_root": run_root.as_posix(),
        "result_directories": len(result_dirs),
        "history_rows": len(history),
        "latest_label": label_order[-1],
        "written_files": [path.relative_to(run_root).as_posix() for path in written_files],
    }
)

# %% [markdown]
# ## Adaptive Pass Summary

# %%
PASS_INDEX = 18

available_passes = history[["pass_index", "label"]].drop_duplicates().sort_values("pass_index")
selected_pass = history[history["pass_index"] == PASS_INDEX].copy()
if selected_pass.empty:
    raise ValueError(
        f"PASS_INDEX={PASS_INDEX} is not available. "
        f"Available: {available_passes['pass_index'].tolist()}"
    )

summary_columns = [
    "label",
    "source_index",
    "interface_type",
    "mask_margin_nm",
    "p_surf_mask_sum",
    "p_surf_mask_sum_micro",
]
adaptive_pass_summary = (
    selected_pass.sort_values(["interface_type", "mask_margin_nm"])[summary_columns]
    .reset_index(drop=True)
)
display(
    {
        "pass_index": PASS_INDEX,
        "label": adaptive_pass_summary["label"].iloc[0],
        "available_pass_indices": available_passes["pass_index"].tolist(),
    }
)
display(adaptive_pass_summary)

adaptive_pass_pivot_micro = adaptive_pass_summary.pivot(
    index="interface_type",
    columns="mask_margin_nm",
    values="p_surf_mask_sum_micro",
).reindex(["MS", "SA", "MA"])
adaptive_pass_pivot_micro.columns = [
    f"{margin_nm} nm" if margin_nm < 1000 else "1 um"
    for margin_nm in adaptive_pass_pivot_micro.columns
]
display(adaptive_pass_pivot_micro)

# %% [markdown]
# ## Last Summary

# %%
last = history[history["pass_index"] == history["pass_index"].max()].copy()
last_summary = (
    last.sort_values(["interface_type", "mask_margin_nm"])[summary_columns]
    .reset_index(drop=True)
)
display(last_summary)

last_pivot_micro = last_summary.pivot(
    index="interface_type",
    columns="mask_margin_nm",
    values="p_surf_mask_sum_micro",
).reindex(["MS", "SA", "MA"])
last_pivot_micro.columns = [
    f"{margin_nm} nm" if margin_nm < 1000 else "1 um" for margin_nm in last_pivot_micro.columns
]
display(last_pivot_micro)
