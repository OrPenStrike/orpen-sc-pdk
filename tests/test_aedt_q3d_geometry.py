from __future__ import annotations

import gdsfactory as gf
import pytest

from orpen_sc_pdk.cells.capacitor import interdigital_capacitor
from orpen_sc_pdk.pdk import PDK
from orpen_sc_pdk.simulation.aedt import prepare_interdigital_capacitor_q3d_geometry
from orpen_sc_pdk.tech import LAYER


def test_idc_q3d_clearance_extends_only_mask_and_etch() -> None:
    PDK.activate()
    base = interdigital_capacitor(terminal_extension_length_um=100.0)
    base_info = base.info.model_dump()
    base_ports = {
        port.name: (port.center, port.width, port.orientation, port.layer, port.port_type)
        for port in base.ports
    }
    base_instance_count = len(base.insts)
    base_regions = {
        layer: base.get_region(layer, merge=True)
        for layer in (
            LAYER.D0_TOP_M1_DRAW,
            LAYER.D0_TOP_GROUND_MASK,
            LAYER.D0_TOP_M1_ETCH,
        )
    }
    prepared = prepare_interdigital_capacitor_q3d_geometry(
        base,
        terminal_open_clearance_um=20.0,
    )

    assert len(prepared.insts) == 0
    assert {port.name for port in prepared.ports} == {
        "o_capacitor_in",
        "o_capacitor_out",
    }
    assert base.info.model_dump() == base_info
    assert len(base.insts) == base_instance_count
    for layer, region in base_regions.items():
        assert (base.get_region(layer, merge=True) ^ region).is_empty()
    assert {
        port.name: (port.center, port.width, port.orientation, port.layer, port.port_type)
        for port in base.ports
    } == base_ports
    assert {
        port.name: (port.center, port.width, port.orientation, port.layer, port.port_type)
        for port in prepared.ports
    } == base_ports

    draw = prepared.get_region(LAYER.D0_TOP_M1_DRAW, merge=True)
    assert (draw ^ base.get_region(LAYER.D0_TOP_M1_DRAW, merge=True)).is_empty()
    assert draw.count() == 2

    dbu = prepared.kcl.dbu
    for layer in (LAYER.D0_TOP_GROUND_MASK, LAYER.D0_TOP_M1_ETCH):
        base_bbox = base.get_region(layer, merge=True).bbox()
        prepared_bbox = prepared.get_region(layer, merge=True).bbox()
        assert (base_bbox.left - prepared_bbox.left) * dbu == pytest.approx(20.0)
        assert (prepared_bbox.right - base_bbox.right) * dbu == pytest.approx(20.0)

    mask = prepared.get_region(LAYER.D0_TOP_GROUND_MASK, merge=True)
    etch = prepared.get_region(LAYER.D0_TOP_M1_ETCH, merge=True)
    expected_mask_delta = gf.Component()
    for name, direction in (("o_capacitor_in", -1.0), ("o_capacitor_out", 1.0)):
        port = base.ports[name]
        clearance = expected_mask_delta << gf.components.rectangle(
            size=(20.0, port.width + 2 * base.info["cpw_gap_um"]),
            centered=True,
            layer=LAYER.D0_TOP_GROUND_MASK,
        )
        clearance.dmove((port.x + direction * 10.0, port.y))
    expected_mask = base_regions[LAYER.D0_TOP_GROUND_MASK].dup()
    expected_mask += expected_mask_delta.get_region(
        LAYER.D0_TOP_GROUND_MASK,
        merge=True,
    )
    expected_mask.merge()
    assert (mask ^ expected_mask).is_empty()
    assert (etch ^ (mask - draw)).is_empty()
    for layer in (
        LAYER.D0_TOP_M1_DRAW,
        LAYER.D0_TOP_GROUND_MASK,
        LAYER.D0_TOP_M1_ETCH,
    ):
        assert (
            prepared.get_region(layer, merge=False).count()
            == prepared.get_region(
                layer,
                merge=True,
            ).count()
        )
    assert prepared.info["cpw_gap_um"] == pytest.approx(6.0)
    assert prepared.info["q3d_terminal_open_clearance_um"] == pytest.approx(20.0)

    with pytest.raises(ValueError, match="finite and positive"):
        prepare_interdigital_capacitor_q3d_geometry(
            base,
            terminal_open_clearance_um=0.0,
        )

    invalid = gf.Component()
    invalid.add_port(
        name="o_capacitor_in",
        center=(-10.0, 0.0),
        width=10.0,
        orientation=180,
        layer=LAYER.D0_TOP_M1_DRAW,
    )
    invalid.add_port(
        name="o_capacitor_out",
        center=(10.0, 0.0),
        width=10.0,
        orientation=0,
        layer=LAYER.D0_TOP_M1_DRAW,
    )
    invalid.info["cpw_gap_um"] = 6.0
    with pytest.raises(ValueError, match="exactly two IDC signal conductors"):
        prepare_interdigital_capacitor_q3d_geometry(
            invalid,
            terminal_open_clearance_um=20.0,
        )

    missing_mask = gf.Component()
    idc_ref = missing_mask << base
    missing_mask.add_ports(idc_ref.ports)
    missing_mask.flatten()
    missing_mask.remove_layers(
        [LAYER.D0_TOP_GROUND_MASK, LAYER.D0_TOP_M1_ETCH],
        recursive=False,
    )
    missing_mask.info["cpw_gap_um"] = 6.0
    with pytest.raises(ValueError, match="ground-mask opening"):
        prepare_interdigital_capacitor_q3d_geometry(
            missing_mask,
            terminal_open_clearance_um=20.0,
        )
