"""Indium bump primitives and keepout-aware bump-field placement."""

import copy
import math
from typing import TypedDict

import gdsfactory as gf

from orpen_sc_pdk.tech import (
    INDIUM_BUMP_SIZE_UM,
    LAYER,
    LAYER_STACK,
    UNDER_BUMP_SIZE_UM,
    Layer,
)


class _IndiumGroundBumpSettingsRecord(TypedDict):
    """Static public settings used by canonical indium bump construction."""

    indium_bump_size: float
    under_bump_size: float
    include_under_bump: bool
    indium_bump_layer: Layer
    under_bump_layer: Layer


class _IndiumGroundBumpKeepoutRecord(TypedDict):
    """Named keepout records intended for consumers."""

    name: str
    layer: Layer
    consumers: tuple[str, ...]


class IndiumGroundBumpSpec(TypedDict):
    """Canonical non-simulation indium bump contract returned to consumers."""

    schema_identity: str
    canonical_component_name: str
    canonical_component_settings: _IndiumGroundBumpSettingsRecord
    material: str
    bump_height_um: float
    collision_footprint_layers: tuple[Layer, ...]
    authored_site_occupancy_layers: tuple[Layer, ...]
    lattice_origin_um: tuple[float, float]
    keepout_records: tuple[_IndiumGroundBumpKeepoutRecord, ...]


def get_indium_ground_bump_spec() -> IndiumGroundBumpSpec:
    """Return canonical indium bump spec metadata.

    `lattice_origin_um=(0.0, 0.0)` is the component-local PDK physical origin.
    `pitch_um` and clearance/margin fields are intentionally absent and are passed
    explicitly by consumers.
    Keepout records preserve each source layer separately; consumers may derive union
    layers for collision or occupancy, but should not replace provenance with unions.
    """
    indium_bump_level = LAYER_STACK["D0_D1_INDIUM_BUMP"]
    fill_spec = copy.deepcopy(indium_bump_level.info["ground_bump_fill_spec"])
    bump_layer = tuple(fill_spec["body_layer"])
    under_bump_layer = tuple(fill_spec["contact_layer"])

    return {
        "schema_identity": "orpen.indium_ground_bump_spec.v1",
        "canonical_component_name": "indium_bump",
        "canonical_component_settings": _IndiumGroundBumpSettingsRecord(
            indium_bump_size=INDIUM_BUMP_SIZE_UM,
            under_bump_size=UNDER_BUMP_SIZE_UM,
            include_under_bump=True,
            indium_bump_layer=bump_layer,
            under_bump_layer=under_bump_layer,
        ),
        "material": str(indium_bump_level.material),
        "bump_height_um": float(indium_bump_level.thickness),
        "collision_footprint_layers": (
            bump_layer,
            under_bump_layer,
        ),
        "authored_site_occupancy_layers": (
            bump_layer,
            under_bump_layer,
        ),
        "lattice_origin_um": tuple(fill_spec["lattice_origin_um"]),
        "keepout_records": tuple(fill_spec["keepout_records"]),
    }


@gf.cell(tags=["elements"])
def indium_bump(
    indium_bump_size: float = INDIUM_BUMP_SIZE_UM,
    under_bump_size: float = UNDER_BUMP_SIZE_UM,
    # Layers
    indium_bump_layer: Layer = LAYER.D0_D1_INDIUM_BUMP,
    under_bump_layer: Layer = LAYER.D0_D1_UNDER_BUMP,
    include_under_bump: bool = True,
) -> gf.Component:
    """Return one indium bump stack centered at the local origin.

    The indium and under-bump pads are authored on separate process layers but
    intentionally expose no route ports; parent chip assemblies place these as
    passive flip-chip interconnect candidates.
    """

    c = gf.Component()
    indium_bump = c << gf.components.rectangle(
        size=(indium_bump_size, indium_bump_size), layer=indium_bump_layer
    )
    indium_bump.move((-indium_bump_size / 2, -indium_bump_size / 2))
    if include_under_bump:
        under_bump = c << gf.components.rectangle(
            size=(under_bump_size, under_bump_size), layer=under_bump_layer
        )
        under_bump.move((-under_bump_size / 2, -under_bump_size / 2))
    c.ports.clear()
    return c


@gf.cell
def indium_ground(
    width: float = 9900.0,
    height: float = 9900.0,
    bump_gap: float = 40.0,
    margin: float = 90.0,
    indium_bump_size: float = INDIUM_BUMP_SIZE_UM,
    under_bump_size: float = UNDER_BUMP_SIZE_UM,
    keepout_region: gf.Region | None = None,
    # Layers
    indium_bump_layer: Layer = LAYER.D0_D1_INDIUM_BUMP,
    under_bump_layer: Layer = LAYER.D0_D1_UNDER_BUMP,
    include_under_bump: bool = True,
) -> gf.Component:
    """Return a regular indium bump field with optional signal-layout keepouts.

    ``keepout_region`` is evaluated against the union of indium and under-bump
    footprints so chip assemblies can add this plane after signal geometry has
    declared the areas that bumps must avoid.
    """

    c = gf.Component()

    footprint_size = (
        max(indium_bump_size, under_bump_size) if include_under_bump else indium_bump_size
    )
    pitch = bump_gap + footprint_size
    usable_width = width - 2 * margin
    usable_height = height - 2 * margin

    if usable_width < footprint_size or usable_height < footprint_size:
        raise ValueError("width and height must leave room for at least one indium bump")

    columns = math.floor((usable_width - footprint_size) / pitch) + 1
    rows = math.floor((usable_height - footprint_size) / pitch) + 1

    bump = indium_bump(
        indium_bump_size=indium_bump_size,
        under_bump_size=under_bump_size,
        indium_bump_layer=indium_bump_layer,
        under_bump_layer=under_bump_layer,
        include_under_bump=include_under_bump,
    )

    if keepout_region is None or keepout_region.is_empty():
        # With no keepout policy, the bump field remains a compact GF array.
        _ = c << gf.components.array(
            component=bump,
            columns=columns,
            rows=rows,
            column_pitch=pitch,
            row_pitch=pitch,
            centered=True,
        )
        return c

    bump_temp = bump.copy()
    bump_temp.flatten()
    bump_footprint = bump_temp.get_region(indium_bump_layer, merge=True)
    if include_under_bump:
        bump_footprint += bump_temp.get_region(under_bump_layer, merge=True)
    bump_footprint = bump_footprint.merged()

    x0 = -((columns - 1) * pitch) / 2
    y0 = -((rows - 1) * pitch) / 2

    for column in range(columns):
        x = x0 + column * pitch
        for row in range(rows):
            y = y0 + row * pitch
            candidate_footprint = bump_footprint.moved(
                round(x / bump_temp.kcl.dbu),
                round(y / bump_temp.kcl.dbu),
            )
            if not (candidate_footprint & keepout_region).is_empty():
                continue

            bump_ref = c << bump
            bump_ref.move((x, y))

    c.ports.clear()
    return c
