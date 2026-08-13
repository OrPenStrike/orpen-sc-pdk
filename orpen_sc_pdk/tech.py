"""Public technology definitions for the OrPen superconducting PDK."""

from collections.abc import Callable
from functools import cache, partial, wraps
from math import isfinite
from typing import Any

import gdsfactory as gf
from doroutes.bundles import add_bundle_astar
from gdsfactory.cross_section import CrossSection
from gdsfactory.technology import DerivedLayer, LayerLevel, LayerMap, LayerStack, LayerViews
from gdsfactory.technology.layer_stack import LogicalLayer
from gdsfactory.typings import ConnectivitySpec, Layer, LayerSpec

from orpen_sc_pdk.config import PATH

nm = 1e-3


class LayerMapOrpenSCPDK(LayerMap):
    """Die and face aware public layer map.

    Layer names intentionally describe process semantics only. Real private
    qubit, resonator, and chip assemblies should live in layout packs.
    """

    D0_BOTTOM_M1_DRAW: Layer = (3, 0)
    D0_BOTTOM_M1_ETCH: Layer = (3, 1)
    D0_TOP_M1_DRAW: Layer = (1, 0)
    D0_TOP_M1_ETCH: Layer = (1, 1)
    D1_BOTTOM_M1_DRAW: Layer = (2, 0)
    D1_BOTTOM_M1_ETCH: Layer = (2, 1)
    D1_TOP_M1_DRAW: Layer = (4, 0)
    D1_TOP_M1_ETCH: Layer = (4, 1)

    D0_D1_INDIUM_BUMP: Layer = (40, 0)
    D0_D1_UNDER_BUMP: Layer = (40, 1)
    D1_D2_INDIUM_BUMP: Layer = (41, 0)
    D1_D2_UNDER_BUMP: Layer = (41, 1)

    D0_BOTTOM_AB_DRAW: Layer = (12, 0)
    D0_BOTTOM_AB_VIA: Layer = (12, 1)
    D0_TOP_AB_DRAW: Layer = (10, 0)
    D0_TOP_AB_VIA: Layer = (10, 1)
    D1_BOTTOM_AB_DRAW: Layer = (11, 0)
    D1_BOTTOM_AB_VIA: Layer = (11, 1)
    D1_TOP_AB_DRAW: Layer = (13, 0)
    D1_TOP_AB_VIA: Layer = (13, 1)

    D0_BOTTOM_JJ_DRAW: Layer = (20, 0)
    D0_TOP_JJ_DRAW: Layer = (21, 0)
    D1_BOTTOM_JJ_DRAW: Layer = (22, 0)
    D1_TOP_JJ_DRAW: Layer = (23, 0)

    D0_TOP_IND: Layer = (30, 0)
    D1_BOTTOM_IND: Layer = (30, 1)
    D0_TOP_TSV: Layer = (31, 0)
    D1_BOTTOM_TSV: Layer = (31, 1)
    DICE: Layer = (70, 0)

    D0_BOTTOM_ALN: Layer = (81, 0)
    D0_TOP_ALN: Layer = (80, 0)
    D1_BOTTOM_ALN: Layer = (83, 0)
    D1_TOP_ALN: Layer = (82, 0)

    D0_BOTTOM_GROUND_MASK: Layer = (111, 0)
    D0_TOP_GROUND_MASK: Layer = (110, 0)
    D1_BOTTOM_GROUND_MASK: Layer = (110, 1)
    D1_TOP_GROUND_MASK: Layer = (111, 1)

    TEXT: Layer = (90, 0)
    LABEL_SETTINGS: Layer = (100, 0)
    LABEL_INSTANCE: Layer = (101, 0)
    WG: Layer = (102, 0)
    ERROR_PATH: Layer = (1000, 0)

    D0_BOTTOM_M1_DOMAIN: Layer = (200, 0)
    D0_TOP_M1_DOMAIN: Layer = (200, 1)
    D1_BOTTOM_M1_DOMAIN: Layer = (200, 2)
    D1_TOP_M1_DOMAIN: Layer = (200, 3)
    D0_SUBSTRATE_AREA: Layer = (201, 0)
    D0_TO_D1_GAP_AREA: Layer = (201, 1)
    D1_SUBSTRATE_AREA: Layer = (201, 2)
    OUTER_VACUUM_AREA: Layer = (201, 3)
    D0_BOTTOM_SIM_BOUNDARY: Layer = (202, 0)
    D0_TOP_SIM_BOUNDARY: Layer = (202, 1)
    D1_BOTTOM_SIM_BOUNDARY: Layer = (202, 2)
    D1_TOP_SIM_BOUNDARY: Layer = (202, 3)


L = LAYER = LayerMapOrpenSCPDK

material_properties = {
    "vacuum": {
        "relative_permittivity": 1.0,
        "permeability": 1.0,
        "material_kind": "vacuum",
    },
    "Si": {
        "relative_permittivity": 11.45,
        "permeability": 1.0,
        "material_kind": "dielectric",
    },
    "Al": {"relative_permittivity": float("inf"), "material_kind": "superconductor"},
    "Nb": {"relative_permittivity": float("inf"), "material_kind": "superconductor"},
    "TiN": {"relative_permittivity": float("inf"), "material_kind": "superconductor"},
    "In": {"relative_permittivity": float("inf"), "material_kind": "superconductor"},
    "AlOx_native_generic": {
        "relative_permittivity": 10.0,
        "permeability": 1.0,
        "material_kind": "dielectric",
    },
}

material_alias_records = {
    "air": "vacuum",
    "silicon": "Si",
}

interface_preset_records = {}

SUBSTRATE_THICKNESS_UM = 500.0
METAL_THICKNESS_UM = 200 * nm
AIRBRIDGE_VIA_THICKNESS_UM = 100 * nm
AIRBRIDGE_THICKNESS_UM = 200 * nm
D0_D1_METAL_FACE_GAP_UM = 9.8
D0_D1_SUBSTRATE_FACE_GAP_UM = D0_D1_METAL_FACE_GAP_UM + 2 * METAL_THICKNESS_UM
OUTER_VACUUM_THICKNESS_UM = 1000.0


def _zmin_from_face(*, face_z: float, outward: int, offset: float, thickness: float) -> float:
    if outward not in {-1, 1}:
        raise ValueError(f"outward must be -1 or +1, got {outward!r}.")
    if outward > 0:
        return face_z + offset
    return face_z - offset - thickness


def _derived_m1_layer(
    *,
    domain_layer: Layer,
    etch_layer: Layer,
    draw_layer: Layer,
) -> DerivedLayer:
    return DerivedLayer(
        layer1=LogicalLayer(layer=domain_layer),
        layer2=DerivedLayer(
            layer1=LogicalLayer(layer=etch_layer),
            layer2=LogicalLayer(layer=draw_layer),
            operation="-",
        ),
        operation="-",
    )


def _m1_layer_level(
    *,
    name: str,
    domain_layer: Layer,
    etch_layer: Layer,
    draw_layer: Layer,
    face_z: float,
    outward: int,
    mesh_order: int,
    info: dict[str, Any] | None = None,
) -> LayerLevel:
    kwargs: dict[str, Any] = {}
    if info is not None:
        kwargs["info"] = info

    return LayerLevel(
        name=name,
        layer=_derived_m1_layer(
            domain_layer=domain_layer,
            etch_layer=etch_layer,
            draw_layer=draw_layer,
        ),
        derived_layer=LogicalLayer(layer=draw_layer),
        thickness=METAL_THICKNESS_UM,
        zmin=_zmin_from_face(
            face_z=face_z,
            outward=outward,
            offset=0.0,
            thickness=METAL_THICKNESS_UM,
        ),
        material="Al",
        mesh_order=mesh_order,
        **kwargs,
    )


def _face_layer_level(
    *,
    name: str,
    layer: Layer,
    face_z: float,
    outward: int,
    offset: float,
    thickness: float,
    material: str,
    mesh_order: int | None = None,
) -> LayerLevel:
    kwargs: dict[str, Any] = {}
    if mesh_order is not None:
        kwargs["mesh_order"] = mesh_order

    return LayerLevel(
        name=name,
        layer=layer,
        thickness=thickness,
        zmin=_zmin_from_face(
            face_z=face_z,
            outward=outward,
            offset=offset,
            thickness=thickness,
        ),
        material=material,
        **kwargs,
    )


def _face_port_sheet_layer_level(
    *,
    name: str,
    layer: Layer,
    face_z: float,
    outward: int,
    mesh_order: int = 15,
) -> LayerLevel:
    return LayerLevel(
        name=name,
        layer=layer,
        thickness=0.0,
        zmin=face_z + outward * METAL_THICKNESS_UM / 2,
        material="vacuum",
        mesh_order=mesh_order,
    )


def _face_layer_levels(
    *,
    die: str,
    face: str,
    face_z: float,
    outward: int,
    m1_domain_layer: Layer,
    m1_draw_layer: Layer,
    m1_etch_layer: Layer,
    airbridge_draw_layer: Layer,
    airbridge_via_layer: Layer,
    sim_boundary_layer: Layer,
    mesh_order: int,
    m1_info: dict[str, Any] | None = None,
) -> dict[str, LayerLevel]:
    prefix = f"{die}_{face}"
    return {
        f"{prefix}_M1": _m1_layer_level(
            name=f"{prefix}_M1",
            domain_layer=m1_domain_layer,
            etch_layer=m1_etch_layer,
            draw_layer=m1_draw_layer,
            face_z=face_z,
            outward=outward,
            mesh_order=mesh_order,
            info=m1_info,
        ),
        f"{prefix}_AIRBRIDGE_VIA": _face_layer_level(
            name=f"{prefix}_AIRBRIDGE_VIA",
            layer=airbridge_via_layer,
            face_z=face_z,
            outward=outward,
            offset=METAL_THICKNESS_UM,
            thickness=AIRBRIDGE_VIA_THICKNESS_UM,
            material="Al",
        ),
        f"{prefix}_AIRBRIDGE": _face_layer_level(
            name=f"{prefix}_AIRBRIDGE",
            layer=airbridge_draw_layer,
            face_z=face_z,
            outward=outward,
            offset=METAL_THICKNESS_UM + AIRBRIDGE_VIA_THICKNESS_UM,
            thickness=AIRBRIDGE_THICKNESS_UM,
            material="Al",
        ),
        f"{prefix}_SIM_BOUNDARY": _face_port_sheet_layer_level(
            name=f"{prefix}_SIM_BOUNDARY",
            layer=sim_boundary_layer,
            face_z=face_z,
            outward=outward,
        ),
    }


@cache
def get_layer_stack() -> LayerStack:
    """Return the public die and face aware layer stack."""

    d0_top_face_z = 0.0
    d0_bottom_face_z = -SUBSTRATE_THICKNESS_UM
    d1_bottom_face_z = D0_D1_SUBSTRATE_FACE_GAP_UM
    d1_substrate_zmin = d1_bottom_face_z
    d1_top_face_z = d1_substrate_zmin + SUBSTRATE_THICKNESS_UM

    return LayerStack(
        layers={
            "D0_SUBSTRATE": LayerLevel(
                name="D0_SUBSTRATE",
                layer=L.D0_SUBSTRATE_AREA,
                thickness=SUBSTRATE_THICKNESS_UM,
                zmin=-SUBSTRATE_THICKNESS_UM,
                material="Si",
                mesh_order=20,
            ),
            "D1_SUBSTRATE": LayerLevel(
                name="D1_SUBSTRATE",
                layer=L.D1_SUBSTRATE_AREA,
                thickness=SUBSTRATE_THICKNESS_UM,
                zmin=d1_substrate_zmin,
                material="Si",
                mesh_order=21,
            ),
            "D0_TO_D1_GAP": LayerLevel(
                name="D0_TO_D1_GAP",
                layer=L.D0_TO_D1_GAP_AREA,
                thickness=D0_D1_SUBSTRATE_FACE_GAP_UM,
                zmin=0.0,
                material="vacuum",
                mesh_order=98,
            ),
            "OUTER_VACUUM": LayerLevel(
                name="OUTER_VACUUM",
                layer=L.OUTER_VACUUM_AREA,
                thickness=OUTER_VACUUM_THICKNESS_UM,
                zmin=d1_top_face_z,
                material="vacuum",
                mesh_order=99,
            ),
            **_face_layer_levels(
                die="D0",
                face="BOTTOM",
                face_z=d0_bottom_face_z,
                outward=-1,
                m1_domain_layer=L.D0_BOTTOM_M1_DOMAIN,
                m1_draw_layer=L.D0_BOTTOM_M1_DRAW,
                m1_etch_layer=L.D0_BOTTOM_M1_ETCH,
                airbridge_draw_layer=L.D0_BOTTOM_AB_DRAW,
                airbridge_via_layer=L.D0_BOTTOM_AB_VIA,
                sim_boundary_layer=L.D0_BOTTOM_SIM_BOUNDARY,
                mesh_order=11,
            ),
            **_face_layer_levels(
                die="D0",
                face="TOP",
                face_z=d0_top_face_z,
                outward=1,
                m1_domain_layer=L.D0_TOP_M1_DOMAIN,
                m1_draw_layer=L.D0_TOP_M1_DRAW,
                m1_etch_layer=L.D0_TOP_M1_ETCH,
                airbridge_draw_layer=L.D0_TOP_AB_DRAW,
                airbridge_via_layer=L.D0_TOP_AB_VIA,
                sim_boundary_layer=L.D0_TOP_SIM_BOUNDARY,
                mesh_order=10,
                m1_info={
                    "layer_type": "conductor",
                    "part_role": "face_metal",
                    "net_id": "Ground",
                    "equipotential_id": "Ground",
                },
            ),
            **_face_layer_levels(
                die="D1",
                face="BOTTOM",
                face_z=d1_bottom_face_z,
                outward=-1,
                m1_domain_layer=L.D1_BOTTOM_M1_DOMAIN,
                m1_draw_layer=L.D1_BOTTOM_M1_DRAW,
                m1_etch_layer=L.D1_BOTTOM_M1_ETCH,
                airbridge_draw_layer=L.D1_BOTTOM_AB_DRAW,
                airbridge_via_layer=L.D1_BOTTOM_AB_VIA,
                sim_boundary_layer=L.D1_BOTTOM_SIM_BOUNDARY,
                mesh_order=12,
                m1_info={
                    "layer_type": "conductor",
                    "part_role": "face_metal",
                    "net_id": "Ground",
                    "equipotential_id": "Ground",
                },
            ),
            **_face_layer_levels(
                die="D1",
                face="TOP",
                face_z=d1_top_face_z,
                outward=1,
                m1_domain_layer=L.D1_TOP_M1_DOMAIN,
                m1_draw_layer=L.D1_TOP_M1_DRAW,
                m1_etch_layer=L.D1_TOP_M1_ETCH,
                airbridge_draw_layer=L.D1_TOP_AB_DRAW,
                airbridge_via_layer=L.D1_TOP_AB_VIA,
                sim_boundary_layer=L.D1_TOP_SIM_BOUNDARY,
                mesh_order=13,
            ),
            "D0_TOP_TSV": LayerLevel(
                name="D0_TOP_TSV",
                layer=L.D0_TOP_TSV,
                thickness=SUBSTRATE_THICKNESS_UM,
                zmin=-SUBSTRATE_THICKNESS_UM,
                material="TiN",
                mesh_order=3,
            ),
            "D1_BOTTOM_TSV": LayerLevel(
                name="D1_BOTTOM_TSV",
                layer=L.D1_BOTTOM_TSV,
                thickness=SUBSTRATE_THICKNESS_UM,
                zmin=d1_substrate_zmin,
                material="TiN",
                mesh_order=3,
            ),
            "D0_TOP_INDIUM": _face_layer_level(
                name="D0_TOP_INDIUM",
                layer=L.D0_TOP_IND,
                face_z=d0_top_face_z,
                outward=1,
                offset=METAL_THICKNESS_UM,
                thickness=D0_D1_METAL_FACE_GAP_UM,
                material="In",
                mesh_order=3,
            ),
            "D1_BOTTOM_INDIUM": _face_layer_level(
                name="D1_BOTTOM_INDIUM",
                layer=L.D1_BOTTOM_IND,
                face_z=d1_bottom_face_z,
                outward=-1,
                offset=METAL_THICKNESS_UM,
                thickness=D0_D1_METAL_FACE_GAP_UM,
                material="In",
                mesh_order=3,
            ),
            "D0_D1_INDIUM_BUMP": LayerLevel(
                name="D0_D1_INDIUM_BUMP",
                layer=L.D0_D1_INDIUM_BUMP,
                thickness=D0_D1_METAL_FACE_GAP_UM,
                zmin=METAL_THICKNESS_UM,
                material="In",
                mesh_order=3,
                info={
                    "layer_type": "via",
                    "part_role": "bump_body",
                    "net_id": "Ground",
                    "equipotential_id": "Ground",
                },
            ),
            "D0_D1_UNDER_BUMP": LayerLevel(
                name="D0_D1_UNDER_BUMP",
                layer=L.D0_D1_UNDER_BUMP,
                thickness=METAL_THICKNESS_UM,
                zmin=0.0,
                material="In",
                mesh_order=3,
                info={
                    "layer_type": "conductor",
                    "part_role": "contact_pad",
                    "attached_face_metal_semantic_id": "D0_TOP_M1",
                    "net_id": "Ground",
                    "equipotential_id": "Ground",
                },
            ),
        }
    )


def get_layer_views() -> LayerViews:
    """Return package layer views from the YAML layer-display source."""

    return LayerViews(PATH.lyp_yaml)


LAYER_STACK = get_layer_stack()
LAYER_VIEWS = get_layer_views()
LAYER_CONNECTIVITY: list[ConnectivitySpec] = [
    ("D0_TOP_M1_DRAW", "D0_TOP_TSV", "D1_BOTTOM_M1_DRAW"),
    ("D0_TOP_M1_DRAW", "D0_TOP_IND", "D1_BOTTOM_M1_DRAW"),
    ("D0_TOP_M1_DRAW", "D0_TOP_AB_DRAW", "D0_TOP_M1_DRAW"),
    ("D1_BOTTOM_M1_DRAW", "D1_BOTTOM_AB_DRAW", "D1_BOTTOM_M1_DRAW"),
]


def get_two_die_flip_chip_layer_stack() -> LayerStack:
    """Return the explicit two-die flip-chip stack."""

    return LAYER_STACK


LAYER_STACK_FLIP_CHIP = get_two_die_flip_chip_layer_stack()

cross_sections: dict[str, Callable[..., CrossSection]] = {}
_cross_section_default_names: dict[str, str] = {}


def xsection(func: Callable[..., CrossSection]) -> Callable[..., CrossSection]:
    """Register a public cross-section with stable default naming."""

    default_cross_section = func()
    _cross_section_default_names[default_cross_section.name] = func.__name__

    @wraps(func)
    def decorated_cross_section(**kwargs: Any) -> CrossSection:
        cross_section = func(**kwargs)
        if cross_section.name in _cross_section_default_names:
            cross_section._name = _cross_section_default_names[cross_section.name]
        return cross_section

    cross_sections[func.__name__] = decorated_cross_section
    return decorated_cross_section


CPW_ETCH_NEG = "cpw_etch_neg"
CPW_DRAW = "cpw_draw"
CPW_ETCH_POS = "cpw_etch_pos"
CPW_GROUND_MASK = "cpw_ground_mask"


@xsection
def coplanar_waveguide(
    width: float = 10.0,
    gap: float = 6.0,
    draw_layer: LayerSpec = LAYER.D0_TOP_M1_DRAW,
    etch_layer: LayerSpec = LAYER.D0_TOP_M1_ETCH,
    ground_mask_layer: LayerSpec = LAYER.D0_TOP_GROUND_MASK,
    radius: float | None = 100.0,
) -> CrossSection:
    """Return the public CPW cross-section with named DRAW/ETCH/MASK sections."""

    if width <= 0:
        raise ValueError(f"width must be positive, got {width!r}.")
    if gap <= 0:
        raise ValueError(f"gap must be positive, got {gap!r}.")

    etch_offset = width / 2 + gap / 2
    ground_mask_width = width + 2 * gap

    etch_neg = gf.Section(
        width=gap,
        offset=-etch_offset,
        layer=etch_layer,
        name=CPW_ETCH_NEG,
    )
    etch_pos = gf.Section(
        width=gap,
        offset=etch_offset,
        layer=etch_layer,
        name=CPW_ETCH_POS,
    )
    ground_mask = gf.Section(
        width=ground_mask_width,
        offset=0.0,
        layer=ground_mask_layer,
        name=CPW_GROUND_MASK,
    )

    return gf.cross_section.cross_section(
        width=width,
        layer=draw_layer,
        main_section_name=CPW_DRAW,
        sections=(etch_neg, etch_pos, ground_mask),
        radius=radius,
    )


def n_trace_coplanar_waveguide(
    trace_widths: tuple[float, ...] = (7.0, 7.0),
    trace_gaps: tuple[float, ...] = (6.0, 6.0),
    inter_trace_ground_widths: tuple[float, ...] = (3.0,),
    *,
    trace_names: tuple[str, ...] | None = None,
    draw_layer: LayerSpec = LAYER.D0_TOP_M1_DRAW,
    etch_layer: LayerSpec = LAYER.D0_TOP_M1_ETCH,
    ground_mask_layer: LayerSpec = LAYER.D0_TOP_GROUND_MASK,
    radius: float | None = 100.0,
) -> CrossSection:
    """Return a multi-trace coplanar-waveguide cross-section with named traces."""

    n_traces = len(trace_widths)
    if n_traces < 2:
        raise ValueError(
            f"n_trace_coplanar_waveguide requires at least two traces, got {n_traces!r}."
        )
    if len(trace_gaps) != n_traces:
        raise ValueError(
            "trace_widths and trace_gaps must have the same length, "
            f"got {n_traces!r} and {len(trace_gaps)!r}."
        )
    if len(inter_trace_ground_widths) != n_traces - 1:
        raise ValueError(
            "inter_trace_ground_widths must contain exactly one value between traces, "
            f"got {len(inter_trace_ground_widths)!r} for {n_traces!r} traces."
        )

    trace_widths_f = tuple(float(value) for value in trace_widths)
    trace_gaps_f = tuple(float(value) for value in trace_gaps)
    inter_trace_ground_widths_f = tuple(float(value) for value in inter_trace_ground_widths)
    for label, values in (
        ("trace_widths", trace_widths_f),
        ("trace_gaps", trace_gaps_f),
        ("inter_trace_ground_widths", inter_trace_ground_widths_f),
    ):
        for index, value in enumerate(values):
            if not isfinite(value) or value <= 0:
                raise ValueError(
                    f"{label}[{index}] must be finite and greater than 0, got {value!r}."
                )
    if radius is not None and (not isfinite(radius) or radius <= 0):
        raise ValueError(f"radius must be finite and greater than 0, got {radius!r}.")

    if trace_names is None:
        trace_names = tuple(f"t{i + 1}" for i in range(n_traces))
    else:
        trace_names = tuple(trace_names)
    if len(trace_names) != n_traces:
        raise ValueError(
            f"trace_names must contain exactly {n_traces} names, got {len(trace_names)!r}."
        )
    for trace_name in trace_names:
        if not isinstance(trace_name, str) or not trace_name.strip():
            raise ValueError("trace_names must be non-empty strings.")
    if len(set(trace_names)) != n_traces:
        raise ValueError("trace_names must be unique.")

    total_footprint_width = (
        2 * sum(trace_gaps_f) + sum(trace_widths_f) + sum(inter_trace_ground_widths_f)
    )
    section_centers = -total_footprint_width / 2

    first_trace_name = trace_names[0]
    first_left_gap = trace_gaps_f[0]
    first_trace_width = trace_widths_f[0]
    sections: list[gf.Section] = [
        gf.Section(
            width=first_left_gap,
            offset=-(section_centers + first_left_gap / 2),
            layer=etch_layer,
            name=f"{first_trace_name}_s_neg",
        )
    ]
    section_centers += first_left_gap
    first_trace_offset = -(section_centers + first_trace_width / 2)
    section_centers += first_trace_width
    sections.append(
        gf.Section(
            width=first_trace_width + 2 * first_left_gap,
            offset=first_trace_offset,
            layer=ground_mask_layer,
            name=CPW_GROUND_MASK,
        )
    )
    sections.append(
        gf.Section(
            width=first_left_gap,
            offset=-(section_centers + first_left_gap / 2),
            layer=etch_layer,
            name=f"{first_trace_name}_s_pos",
        )
    )
    section_centers += first_left_gap
    if n_traces > 1:
        section_centers += inter_trace_ground_widths_f[0]

    for trace_index in range(1, n_traces):
        left_gap = trace_gaps_f[trace_index]
        trace_width = trace_widths_f[trace_index]
        trace_name = trace_names[trace_index]
        sections.append(
            gf.Section(
                width=left_gap,
                offset=-(section_centers + left_gap / 2),
                layer=etch_layer,
                name=f"{trace_name}_s_neg",
            )
        )
        section_centers += left_gap
        sections.append(
            gf.Section(
                width=trace_width,
                offset=-(section_centers + trace_width / 2),
                layer=draw_layer,
                name=trace_name,
                port_names=(f"{trace_name}_o1", f"{trace_name}_o2"),
            )
        )
        trace_offset = -(section_centers + trace_width / 2)
        sections.append(
            gf.Section(
                width=trace_width + 2 * left_gap,
                offset=trace_offset,
                layer=ground_mask_layer,
                name=f"{trace_name}_ground_mask",
            )
        )
        section_centers += trace_width
        sections.append(
            gf.Section(
                width=left_gap,
                offset=-(section_centers + left_gap / 2),
                layer=etch_layer,
                name=f"{trace_name}_s_pos",
            )
        )
        section_centers += left_gap
        if trace_index < n_traces - 1:
            inter_ground = inter_trace_ground_widths_f[trace_index]
            section_centers += inter_ground
    return gf.cross_section.cross_section(
        width=trace_widths_f[0],
        layer=draw_layer,
        offset=first_trace_offset,
        main_section_name=trace_names[0],
        port_names=(f"{trace_names[0]}_o1", f"{trace_names[0]}_o2"),
        sections=tuple(sections),
        radius=radius,
    )


cross_sections["n_trace_coplanar_waveguide"] = n_trace_coplanar_waveguide

cpw = coplanar_waveguide
etch = etch_only = partial(
    coplanar_waveguide,
    draw_layer=LAYER.D0_TOP_M1_ETCH,
    etch_layer=LAYER.D0_TOP_M1_ETCH,
    ground_mask_layer=LAYER.D0_TOP_M1_ETCH,
)


@xsection
def cpw_2dot7_4_2dot7(
    width: float = 4.0,
    draw_layer: LayerSpec = LAYER.D0_TOP_M1_DRAW,
    etch_layer: LayerSpec = LAYER.D0_TOP_M1_ETCH,
    ground_mask_layer: LayerSpec = LAYER.D0_TOP_GROUND_MASK,
    radius: float | None = 100.0,
) -> CrossSection:
    """Return a symmetric CPW cross-section with 2.7-4-2.7 widths."""

    return coplanar_waveguide(
        width=width,
        gap=2.7,
        draw_layer=draw_layer,
        etch_layer=etch_layer,
        ground_mask_layer=ground_mask_layer,
        radius=radius,
    )


@xsection
def cpw_6_10_6(
    width: float = 10.0,
    draw_layer: LayerSpec = LAYER.D0_TOP_M1_DRAW,
    etch_layer: LayerSpec = LAYER.D0_TOP_M1_ETCH,
    ground_mask_layer: LayerSpec = LAYER.D0_TOP_GROUND_MASK,
    radius: float | None = 100.0,
) -> CrossSection:
    """Return a symmetric CPW cross-section with 6-10-6 widths."""

    return coplanar_waveguide(
        width=width,
        gap=6.0,
        draw_layer=draw_layer,
        etch_layer=etch_layer,
        ground_mask_layer=ground_mask_layer,
        radius=radius,
    )


@xsection
def cpw_6_7_6(
    width: float = 7.0,
    draw_layer: LayerSpec = LAYER.D0_TOP_M1_DRAW,
    etch_layer: LayerSpec = LAYER.D0_TOP_M1_ETCH,
    ground_mask_layer: LayerSpec = LAYER.D0_TOP_GROUND_MASK,
    radius: float | None = 100.0,
) -> CrossSection:
    """Return a symmetric CPW cross-section with 6-7-6 widths."""

    return coplanar_waveguide(
        width=width,
        gap=6.0,
        draw_layer=draw_layer,
        etch_layer=etch_layer,
        ground_mask_layer=ground_mask_layer,
        radius=radius,
    )


@xsection
def coupled_cpw_w7_s6_d3(
    *,
    trace_names: tuple[str, ...] | None = None,
    draw_layer: LayerSpec = LAYER.D0_TOP_M1_DRAW,
    etch_layer: LayerSpec = LAYER.D0_TOP_M1_ETCH,
    ground_mask_layer: LayerSpec = LAYER.D0_TOP_GROUND_MASK,
    radius: float | None = 100.0,
) -> CrossSection:
    """Return a thin two-trace coupled-coplanar-waveguide cross-section."""

    return n_trace_coplanar_waveguide(
        trace_widths=(7.0, 7.0),
        trace_gaps=(6.0, 6.0),
        inter_trace_ground_widths=(3.0,),
        trace_names=trace_names,
        draw_layer=draw_layer,
        etch_layer=etch_layer,
        ground_mask_layer=ground_mask_layer,
        radius=radius,
    )


@xsection
def cpw_15_5_15(
    width: float = 5.0,
    gap: float = 15.0,
    draw_layer: LayerSpec = LAYER.D1_BOTTOM_M1_DRAW,
    etch_layer: LayerSpec = LAYER.D1_BOTTOM_M1_ETCH,
    ground_mask_layer: LayerSpec = LAYER.D1_BOTTOM_GROUND_MASK,
    radius: float | None = 100.0,
) -> CrossSection:
    """Return the floating-coupler CPW cross-section with 15-5-15 widths."""

    return coplanar_waveguide(
        width=width,
        gap=gap,
        draw_layer=draw_layer,
        etch_layer=etch_layer,
        ground_mask_layer=ground_mask_layer,
        radius=radius,
    )


@xsection
def launcher_cross_section_big() -> CrossSection:
    """Return a large CPW cross-section for launcher geometry."""

    return coplanar_waveguide(
        width=200.0,
        gap=110.0,
        etch_layer=LAYER.D0_TOP_M1_ETCH,
    )


@xsection
def josephson_junction_cross_section_wide() -> CrossSection:
    """Return the wide Josephson junction wire cross-section."""

    return gf.cross_section.cross_section(
        width=0.2,
        layer=LAYER.D0_TOP_JJ_DRAW,
    )


@xsection
def josephson_junction_cross_section_narrow() -> CrossSection:
    """Return the narrow Josephson junction wire cross-section."""

    return gf.cross_section.cross_section(
        width=0.09,
        layer=LAYER.D0_TOP_JJ_DRAW,
    )


@xsection
def microstrip(
    width: float = 10.0,
    layer: LayerSpec = "D0_TOP_M1_DRAW",
) -> CrossSection:
    """Return an additive metal cross-section."""

    return gf.cross_section.cross_section(
        width=width,
        layer=layer,
    )


strip = strip_metal = microstrip

route_single = route_single_cpw = partial(
    gf.routing.route_single,
    cross_section=cpw,
    bend="bend_circular",
)
route_bundle = route_bundle_cpw = partial(
    gf.routing.route_bundle,
    cross_section=cpw,
    bend="bend_circular",
)
route_single_sbend = route_single_sbend_cpw = partial(
    gf.routing.route_single_sbend,
    cross_section=cpw,
    bend_s="bend_s",
)
route_bundle_all_angle = route_bundle_all_angle_cpw = partial(
    gf.routing.route_bundle_all_angle,
    cross_section=cpw,
    separation=3,
    bend="bend_circular_all_angle",
    straight="straight_all_angle",
)
route_bundle_sbend = route_bundle_sbend_cpw = partial(
    gf.routing.route_bundle_sbend,
    cross_section=cpw,
    bend_s="bend_s",
)
route_astar = route_astar_cpw = partial(
    add_bundle_astar,
    layers=["D0_TOP_M1_ETCH"],
    bend="bend_circular",
    straight="straight",
    grid_unit=500,
    spacing=3,
)
routing_strategies: dict[str, Callable[..., object]] = {
    "route_single": route_single,
    "route_single_cpw": route_single_cpw,
    "route_single_sbend": route_single_sbend,
    "route_bundle": route_bundle,
    "route_bundle_cpw": route_bundle_cpw,
    "route_bundle_all_angle": route_bundle_all_angle,
    "route_bundle_all_angle_cpw": route_bundle_all_angle_cpw,
    "route_bundle_sbend": route_bundle_sbend,
    "route_bundle_sbend_cpw": route_bundle_sbend_cpw,
    "route_astar": route_astar,
    "route_astar_cpw": route_astar_cpw,
}

gf.CONF.layer_error_path = L.ERROR_PATH

__all__ = [
    "CPW_DRAW",
    "CPW_ETCH_NEG",
    "CPW_ETCH_POS",
    "CPW_GROUND_MASK",
    "L",
    "LAYER",
    "LAYER_CONNECTIVITY",
    "LAYER_STACK",
    "LAYER_STACK_FLIP_CHIP",
    "LAYER_VIEWS",
    "Layer",
    "LayerMapOrpenSCPDK",
    "LayerSpec",
    "coplanar_waveguide",
    "n_trace_coplanar_waveguide",
    "coupled_cpw_w7_s6_d3",
    "cpw_15_5_15",
    "cpw_2dot7_4_2dot7",
    "cpw_6_10_6",
    "cpw_6_7_6",
    "cpw",
    "cross_sections",
    "etch",
    "etch_only",
    "get_layer_stack",
    "get_layer_views",
    "get_two_die_flip_chip_layer_stack",
    "josephson_junction_cross_section_narrow",
    "josephson_junction_cross_section_wide",
    "launcher_cross_section_big",
    "interface_preset_records",
    "material_alias_records",
    "material_properties",
    "microstrip",
    "route_astar",
    "route_astar_cpw",
    "route_bundle",
    "route_bundle_all_angle",
    "route_bundle_all_angle_cpw",
    "route_bundle_cpw",
    "route_bundle_sbend",
    "route_bundle_sbend_cpw",
    "route_single",
    "route_single_cpw",
    "route_single_sbend",
    "route_single_sbend_cpw",
    "routing_strategies",
    "strip",
    "strip_metal",
    "xsection",
]
