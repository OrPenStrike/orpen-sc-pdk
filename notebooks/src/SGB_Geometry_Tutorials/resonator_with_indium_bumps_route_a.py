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
# # Public SGB Resonator with Indium Bumps Route A
#
# This notebook recreates one public OrPen PDK geometry fixture for
# the Semantic Geometry Builder tutorial route `A`. It writes a
# fresh GDS file, checks it against the reviewed stack JSON contract,
# and leaves the optional XAO build step explicit.
#
# It does not run Palace, meshing, or Surface EPR inset analysis.

# %%
from __future__ import annotations

import json
import warnings

import gdsfactory as gf
import gdstk
from IPython.display import display
from semantic_geometry_builder import build_gds_stack_geometry_input

from orpen_sc_pdk.cells.chips import resonator_with_indium_bumps
from orpen_sc_pdk.config import PATH
from orpen_sc_pdk.pdk import PDK

warnings.filterwarnings("ignore", message=".*ignored for cross_section.*")

PDK.activate()

GEOMETRY_ID = "resonator_with_indium_bumps"
ROUTE = "A"
TOP_CELL_NAME = "resonator_with_indium_bumps_fixture"
BUILD_SUPPORTED = True
RUN_SGB_BUILDER = False

NOTEBOOK_ROOT = (
    PATH.simulation
    / "notebooks"
    / "SGB_Geometry_Tutorials"
    / GEOMETRY_ID
    / f"route_{ROUTE.lower()}"
)
GDS_DIR = NOTEBOOK_ROOT / "gds"
STACK_DIR = PATH.repo / "notebooks" / "assets" / "semantic_geometry_builder"
GDS_DIR.mkdir(parents=True, exist_ok=True)

# %% [markdown]
# ## Geometry

# %%
gf.clear_cache()
component = (
    resonator_with_indium_bumps(
        resonator_length=4500.0,
    )
).copy()
component.name = TOP_CELL_NAME

display(
    {
        "geometry_id": GEOMETRY_ID,
        "route": ROUTE,
        "top_cell_name": TOP_CELL_NAME,
        "bbox_um": str(component.bbox()),
        "ports": len(component.ports),
    }
)

# %% [markdown]
# ## GDS + stack contract check

# %%
gds_file = GDS_DIR / f"{GEOMETRY_ID}.gds"
stack_file = STACK_DIR / f"{GEOMETRY_ID}.stack.json"

component.write_gds(gds_file)
build_input = build_gds_stack_geometry_input(
    gds_file=gds_file,
    stack_file=stack_file,
    top_cell_name=TOP_CELL_NAME,
    metadata={
        "source_pdk": "orpen_sc_pdk",
        "notebook": f"SGB_Geometry_Tutorials/{GEOMETRY_ID}_route_{ROUTE.lower()}",
        "route": ROUTE,
    },
)

stack = json.loads(stack_file.read_text())
stack_metadata = stack.get("metadata", {})
stack_layers = {
    (int(record["layer"]), int(record["datatype"])) for record in stack.get("layers", [])
}
ignored_layers = {
    (int(record["layer"]), int(record["datatype"]))
    for record in stack_metadata.get("ignored_layout_layers", [])
}
deferred_layers = {
    (int(record["layer"]), int(record["datatype"]))
    for record in stack_metadata.get("deferred_high_count_layers", [])
}
port_sheet_layers = {
    (int(record["layer"]), int(record["datatype"]))
    for record in stack_metadata.get("port_sheet_source_layers", [])
}

library = gdstk.read_gds(str(gds_file))
cell = next(cell for cell in library.cells if cell.name == TOP_CELL_NAME)
gds_layers = {
    (int(polygon.layer), int(polygon.datatype))
    for polygon in cell.get_polygons(apply_repetitions=True)
}
unclassified_layers = sorted(
    gds_layers - stack_layers - ignored_layers - deferred_layers - port_sheet_layers
)

assert not unclassified_layers
assert build_input.polygons
assert build_input.entities

display(
    {
        "geometry_id": GEOMETRY_ID,
        "route": ROUTE,
        "gds_file": gds_file.relative_to(PATH.repo).as_posix(),
        "stack_file": stack_file.relative_to(PATH.repo).as_posix(),
        "polygons": len(build_input.polygons),
        "entities": len(build_input.entities),
        "gds_layers": sorted(gds_layers),
        "unclassified_layers": unclassified_layers,
    }
)

# %% [markdown]
# ## Optional SGB XAO build

# %%
if RUN_SGB_BUILDER and BUILD_SUPPORTED:
    from semantic_geometry_builder import SemanticGeometryBuilder

    run_folder = NOTEBOOK_ROOT / "sgb"
    groups = SemanticGeometryBuilder().build(
        build_input,
        route=ROUTE,
        run_folder=run_folder,
    )
    xao_path = run_folder / "geometry" / f"semantic_geometry_route_{ROUTE.lower()}.xao"
    assert xao_path.is_file()
    display(
        {
            "geometry_id": GEOMETRY_ID,
            "route": ROUTE,
            "xao_path": xao_path.relative_to(PATH.repo).as_posix(),
            "physical_groups": len(groups),
        }
    )
elif RUN_SGB_BUILDER:
    print("Builder intentionally skipped for this high-count fixture.")
elif BUILD_SUPPORTED:
    print("Set RUN_SGB_BUILDER = True to write this route's XAO file.")
else:
    print("This high-count fixture is coverage-only in this notebook.")
