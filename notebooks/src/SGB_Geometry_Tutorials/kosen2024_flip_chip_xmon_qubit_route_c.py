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
#       jupytext_version: 1.19.3
# ---

# %% [markdown]
# # Public SGB Kosen 2024 Flip-chip Xmon Qubit Route C
#
# This notebook builds one public geometry fixture with route `C` and writes a
# reviewable GeometryBuildInput contract into the notebook `input` directory.

# %%
from __future__ import annotations

import warnings
from pathlib import Path

import gdsfactory as gf
from gsim.common.stack.extractor import extract_layer_stack
from IPython.display import display
from semantic_geometry_builder import build_gdsfactory_geometry_input

from orpen_sc_pdk import LAYER_STACK, PATH, PDK
from orpen_sc_pdk.cells import kosen2024_flip_chip_xmon_qubit

warnings.filterwarnings("ignore", message=".*ignored for cross_section.*")

PDK.activate()

GEOMETRY_ID = "kosen2024_flip_chip_xmon_qubit"
ROUTE = "C"
TOP_CELL_NAME = "kosen2024_flip_chip_xmon_qubit_fixture"
RUN_SGB_BUILDER = False

NOTEBOOK_ROOT = (
    PATH.simulation
    / "notebooks"
    / "SGB_Geometry_Tutorials"
    / GEOMETRY_ID
    / f"route_{ROUTE.lower()}"
)
WORK_DIR = NOTEBOOK_ROOT / "input"
WORK_DIR.mkdir(parents=True, exist_ok=True)

# %% [markdown]
# ## Geometry

# %%
gf.clear_cache()
component = kosen2024_flip_chip_xmon_qubit().copy()
component.name = TOP_CELL_NAME

display(
    {
        "geometry_id": GEOMETRY_ID,
        "route": ROUTE,
        "top_cell_name": TOP_CELL_NAME,
        "ports": len(component.ports),
        "bbox_um": str(component.dbbox()),
    }
)

# %% [markdown]
# ## Geometry build input

# %%
build_input = build_gdsfactory_geometry_input(
    component=component,
    layer_stack=extract_layer_stack(LAYER_STACK, pdk_name="orpen_sc_pdk"),
    top_cell_name=TOP_CELL_NAME,
    work_dir=WORK_DIR,
    metadata={
        "source_pdk": "orpen_sc_pdk",
        "notebook": f"SGB_Geometry_Tutorials/{GEOMETRY_ID}/route_{ROUTE.lower()}",
        "route": ROUTE,
    },
)

gds_file = Path(build_input.metadata["generated_gds_file"])
stack_file = Path(build_input.metadata["generated_stack_file"])

assert gds_file.is_file()
assert stack_file.is_file()
assert build_input.polygons
assert build_input.entities
assert build_input.solution_regions

display(
    {
        "geometry_id": GEOMETRY_ID,
        "route": ROUTE,
        "gds_file": gds_file.relative_to(PATH.repo).as_posix(),
        "stack_file": stack_file.relative_to(PATH.repo).as_posix(),
        "polygons": len(build_input.polygons),
        "entities": len(build_input.entities),
        "solution_regions": list(build_input.solution_regions),
    }
)

# %% [markdown]
# ## Optional SGB builder

# %%
if RUN_SGB_BUILDER:
    from semantic_geometry_builder import SemanticGeometryBuilder

    run_folder = NOTEBOOK_ROOT / "sgb"
    groups = SemanticGeometryBuilder().build(
        build_input,
        route=ROUTE,
        run_folder=run_folder,
    )
    display(
        {
            "geometry_id": GEOMETRY_ID,
            "route": ROUTE,
            "run_folder": run_folder.relative_to(PATH.repo).as_posix(),
            "groups": len(groups),
        }
    )
else:
    print("Set RUN_SGB_BUILDER = True to write XAO artifacts.")
