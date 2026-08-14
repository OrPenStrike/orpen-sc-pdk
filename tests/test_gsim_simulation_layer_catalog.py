"""Tests for Public PDK simulation-layer catalogs consumed by gsim."""

from __future__ import annotations

import orpen_sc_pdk.simulation as simulation
import orpen_sc_pdk.simulation.palace_layers as palace_layers
from orpen_sc_pdk.simulation import (
    get_gsim_palace_simulation_layer_catalog,
)
from orpen_sc_pdk.tech import LAYER


def test_public_palace_simulation_layer_catalog_is_gsim_compatible() -> None:
    catalog = get_gsim_palace_simulation_layer_catalog()

    assert set(catalog) == {
        "D0_BOTTOM_SIM_BOUNDARY",
        "D0_TOP_SIM_BOUNDARY",
        "D1_BOTTOM_SIM_BOUNDARY",
        "D1_TOP_SIM_BOUNDARY",
    }
    assert catalog["D0_TOP_SIM_BOUNDARY"] == {
        "gds_layer": (
            LAYER.D0_TOP_SIM_BOUNDARY.layer,
            LAYER.D0_TOP_SIM_BOUNDARY.datatype,
        ),
        "role": "solver_boundary_sheet",
        "stack_layer": "D0_TOP_SIM_BOUNDARY",
    }


def test_public_simulation_layer_catalog_does_not_name_global_surface_epr_bands() -> None:
    catalog = get_gsim_palace_simulation_layer_catalog()

    assert len(catalog) == 4
    assert "surface_epr_band" not in {entry["role"] for entry in catalog.values()}
    assert all("SURFACE_EPR_BAND" not in name for name in catalog)
    assert len({tuple(value["gds_layer"]) for value in catalog.values()}) == len(catalog)


def test_public_catalog_does_not_reserve_generated_surface_epr_face_layers() -> None:
    assert not hasattr(simulation, "get_gsim_palace_surface_epr_layer_number")
    assert not hasattr(palace_layers, "get_gsim_palace_surface_epr_layer_number")
    assert not hasattr(palace_layers, "PALACE_SURFACE_EPR_FACE_LAYER_NUMBERS")
