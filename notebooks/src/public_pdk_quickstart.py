# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.17.3
# ---

# %% [markdown]
# # Public PDK quickstart
#
# This notebook demonstrates the open PDK surface that is safe to publish:
# process semantics, public demo components, and the private-project boundary.
# Private chip layouts and GDS inputs from private designs are intentionally
# outside this repository.

# %%
from IPython.display import display

import orpen_sc_pdk
from orpen_sc_pdk import PDK
from orpen_sc_pdk.cells import cpw_straight, interdigital_capacitor

orpen_sc_pdk.activate()


def port_names(component):
    return sorted(port.name for port in component.ports)


# %% [markdown]
# ## Public demo cells
#
# The PDK can create small public superconducting RF primitives without loading
# any private layout package.

# %%
cpw = cpw_straight(length=500, signal_width=10, gap=6)
capacitor = interdigital_capacitor(fingers=6)

display(
    {
        "cpw": {"name": cpw.name, "ports": port_names(cpw)},
        "capacitor": {"name": capacitor.name, "ports": port_names(capacitor)},
    }
)

# %% [markdown]
# ## Public PDK registry
#
# The public PDK registry contains only publication-safe OrPen cells. Private
# cells belong to a private GF+ project that uses this package as its Base PDK.

# %%
display(
    {
        "public_cells": sorted(PDK.cells),
        "generic_cell_leakage": sorted(
            {"add_frame", "align_wafer", "awg", "bend_euler", "rounded_rectangle"} & set(PDK.cells)
        ),
    }
)

# %% [markdown]
# ## Private layout boundary
#
# Private designs should be packaged separately. For GF+ preview, open the
# private repository as the active project and install `orpen-sc-pdk` as its
# Base PDK. This notebook does not import or name any private layout package.
