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
# process semantics, public demo components, and the static private-mount
# boundary. Private chip layouts and GDS inputs from private designs are
# intentionally outside this repository.

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
# The public PDK registry contains publication-safe cells. Private cells appear
# here only when an ignored local private mount is present during import.

# %%
display(
    {
        "public_cells": sorted(name for name in PDK.cells if not name.startswith("as_")),
        "private_mount_present": "as_resonator" in PDK.cells,
    }
)

# %% [markdown]
# ## Private layout boundary
#
# Private designs should be packaged separately. For GF+ preview, the public PDK
# may re-export an ignored local clone under `orpen_sc_pdk/cells/privates/`.
# This notebook does not import or name any private layout package.
