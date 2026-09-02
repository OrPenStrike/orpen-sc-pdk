# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.3
# ---

# %% [markdown]
# # Read-only Palace Geometry Viewer
# Diagnostic inspection tool for an existing public Palace run; it does not build or run a
# simulation.

# %%
from pathlib import Path

from scgsim.visualization import inspect_palace_geometry

RUN_DIR = Path("EDIT_ME")  # Set this to an existing Palace run folder.
PREVIEW_MODE = "boundaries"  # materials | boundaries | surface_epr | mesh

preview = inspect_palace_geometry(RUN_DIR)
preview.explore(PREVIEW_MODE)
