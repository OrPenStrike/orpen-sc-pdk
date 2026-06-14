"""Port metadata schemas authored while building layout components."""

from enum import StrEnum
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

MetaData = Any


class ParameterModel(BaseModel):
    """Provide immutable validation for layout-authored metadata schemas.

    Use when a helper needs a small, serializable schema before writing values
    into ``port.info``; solver workflow parameter objects stay outside the
    public layout-cell package.

    Example:
        MeshPortInfo(mesh_profile=MeshProfile.METAL_ISLAND).to_info()
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    def to_kwargs(self) -> dict[str, Any]:
        """Return a shallow field mapping for callers that need kwargs.

        Use when a layout metadata object must be passed into another validated
        constructor without recursively converting nested models.

        Example:
            PalaceLumpedPort(direction=AxisDirection.POS_X).to_kwargs()
        """

        return {field_name: getattr(self, field_name) for field_name in self.__class__.model_fields}


class MeshProfile(StrEnum):
    """Name mesh-refinement policies stored as stable layout metadata.

    Use when a cell knows the mesh intent of a polygon before any scene builder
    runs; consumers map these names to Gmsh Native mesh settings later.

    Example:
        MeshPortInfo(mesh_profile=MeshProfile.CRITICAL_METAL_TRACE).to_info()
    """

    SUBMICRON_METAL_TRACE = "submicron_metal_trace"
    CRITICAL_METAL_TRACE = "critical_metal_trace"
    METAL_ISLAND = "metal_island"
    GROUND_PLANE = "ground_plane"
    BULK_DOMAIN = "bulk_domain"
    SOLVER_BOUNDARY_SHEET = "solver_boundary_sheet"


class SimulationPortType(StrEnum):
    """Define repository port_type strings used by layout-authored ports.

    Use when a component writes ports that later scene builders can collect by
    semantic role without guessing from names or layers.

    Example:
        component.add_port("o_jj", port_type=SimulationPortType.JUNCTION_LUMPED)
    """

    CPW = "sim_cpw"
    MESH = "sim_mesh"
    PALACE_TERMINAL = "sim_terminal"
    PALACE_LUMPED = "sim_lumped"
    JUNCTION_LUMPED = "sim_junction_lumped"
    PALACE_WAVE = "sim_wave"
    PALACE_CURRENT = "sim_current"
    Q2D_CONDUCTOR = "sim_q2d_conductor"


class Q2dConductorType(StrEnum):
    """Name exact ANSYS Q2D conductor roles stored on marker ports.

    Use the AEDT UI labels so layout-authored conductor intent can be passed
    through package sidecars without a second translation vocabulary.

    Example:
        Q2dConductorPortInfo(
            conductor_type=Q2dConductorType.REFERENCE_GROUND,
        ).to_info()
    """

    SIGNAL_LINE = "Signal Line"
    REFERENCE_GROUND = "Reference Ground"
    NON_IDEAL_GROUND = "Non Ideal Ground"
    FLOATING_LINE = "Floating Line"
    SURFACE_GROUND = "Surface Ground"


class AxisDirection(StrEnum):
    """Represent axis-aligned sheet or lumped-port directions in port metadata.

    Use when a layout-authored port should carry a solver-facing direction that
    is still independent of any concrete Palace config file.

    Example:
        PalaceLumpedPort(direction=AxisDirection.POS_X).to_info()
    """

    POS_X = "+X"
    NEG_X = "-X"
    POS_Y = "+Y"
    NEG_Y = "-Y"
    POS_Z = "+Z"
    NEG_Z = "-Z"


class CoordinateSystem(StrEnum):
    """Represent solver vector coordinate systems stored on layout ports.

    Use when Palace needs a non-default interpretation for a direction stored
    in ``port.info``; most layout cells can omit it.

    Example:
        PalaceLumpedPort(coordinate_system=CoordinateSystem.CARTESIAN).to_info()
    """

    CARTESIAN = "Cartesian"
    CYLINDRICAL = "Cylindrical"


class MeshPortInfo(ParameterModel):
    """Serialize mesh marker metadata for ``SimulationPortType.MESH`` ports.

    Use when a cell marks simulation-facing geometry with a reusable mesh
    profile. Optional width metadata lets scene builders size in-plane mesh
    from layout intent before falling back to geometry inference.

    Example:
        MeshPortInfo(
            mesh_profile=MeshProfile.METAL_ISLAND,
            feature_width_um=100.0,
        ).to_info()
    """

    mesh_profile: MeshProfile | str
    feature_width_um: float | None = None
    elements_per_width: float | None = None
    curve_min_elements: float | None = None
    curve_element_count_enabled: bool | None = None

    def to_info(self) -> dict[str, MetaData]:
        """Serialize this object into a GDSFactory ``port.info`` payload.

        Use when a component has just added a simulation port and needs a
        stable mesh payload for downstream scene builders.

        Example:
            port.info.update(MeshPortInfo(mesh_profile=MeshProfile.METAL_ISLAND).to_info())
        """

        info: dict[str, MetaData] = {
            "mesh_profile": _metadata_value("mesh_profile", self.mesh_profile),
        }
        _add_optional_positive(info, "mesh_feature_width_um", self.feature_width_um)
        _add_optional_positive(info, "mesh_elements_per_width", self.elements_per_width)
        _add_optional_positive(info, "mesh_curve_min_elements", self.curve_min_elements)
        if self.curve_element_count_enabled is not None:
            info["mesh_curve_element_count_enabled"] = self.curve_element_count_enabled
        return info

    def to_dict(self) -> dict[str, MetaData]:
        """Return ``to_info()`` for callers that prefer dictionary naming.

        Use when older component code expects a dict-like serializer while the
        canonical GDSFactory target remains ``port.info``.

        Example:
            port.info.update(MeshPortInfo(mesh_profile=profile).to_dict())
        """

        return self.to_info()


class Q2dConductorPortInfo(ParameterModel):
    """Serialize Q2D conductor marker metadata for layout-authored ports.

    Use when a component knows which imported conductor should become a Q2D
    assignment. Markers sharing the same ``assignment_name`` and
    ``conductor_type`` become one AEDT Q2D conductor assignment.

    Example:
        Q2dConductorPortInfo(
            conductor_type=Q2dConductorType.SIGNAL_LINE,
            assignment_name="Signal",
        ).to_info()
    """

    conductor_type: Q2dConductorType
    assignment_name: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _default_reference_ground_assignment(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        conductor_type = data.get("conductor_type")
        if isinstance(conductor_type, StrEnum):
            conductor_type = conductor_type.value
        if str(conductor_type) != Q2dConductorType.REFERENCE_GROUND.value:
            return data
        assignment_name = data.get("assignment_name")
        if assignment_name is None or not str(assignment_name).strip():
            return {**data, "assignment_name": "Ground"}
        return data

    @field_validator("assignment_name", mode="before")
    @classmethod
    def _normalize_assignment_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @model_validator(mode="after")
    def _validate_assignment_name(self) -> "Q2dConductorPortInfo":
        if self.assignment_name is None:
            msg = "assignment_name is required for Q2D conductor types other than Reference Ground."
            raise ValueError(msg)
        return self

    def to_info(self) -> dict[str, MetaData]:
        """Serialize this object into a GDSFactory ``port.info`` payload.

        Use after creating a ``sim_q2d_conductor`` marker port so downstream
        AEDT packaging can export conductor sidecars without guessing names.

        Example:
            port.info.update(Q2dConductorPortInfo(
                conductor_type=Q2dConductorType.REFERENCE_GROUND,
            ).to_info())
        """

        return {
            "q2d_conductor_type": self.conductor_type.value,
            "q2d_assignment_name": self.assignment_name,
        }

    def to_dict(self) -> dict[str, MetaData]:
        """Return ``to_info()`` for callers that prefer dictionary naming.

        Use when code wants a serializable payload before writing it into
        ``port.info``.

        Example:
            Q2dConductorPortInfo(
                conductor_type="Signal Line",
                assignment_name="Signal",
            ).to_dict()
        """

        return self.to_info()


class PalaceLumpedPort(ParameterModel):
    """Serialize Palace lumped-port defaults stored on layout ports.

    Use when a component can define stable physical defaults such as direction
    or nominal L/C/R before notebook sweeps or Palace config generation.

    Example:
        PalaceLumpedPort(direction=AxisDirection.POS_X, R=50.0).to_info()
    """

    direction: AxisDirection | str | list[float] | None = None
    coordinate_system: CoordinateSystem | Literal["Cartesian", "Cylindrical"] | None = None
    L: float | None = None
    C: float | None = None
    R: float | None = None
    Ls: float | None = None
    Cs: float | None = None
    Rs: float | None = None
    excitation: bool | int | None = None
    active: bool | None = None

    def to_info(self) -> dict[str, MetaData]:
        """Serialize this object into a GDSFactory ``port.info`` payload.

        Use when a layout port should carry reusable Palace defaults while
        still letting simulations override them later.

        Example:
            port.info.update(PalaceLumpedPort(direction=AxisDirection.POS_X).to_info())
        """

        info: dict[str, MetaData] = {}
        if self.direction is not None:
            if isinstance(self.direction, list):
                info["palace_lumped_port_direction"] = self.direction
            else:
                info["palace_lumped_port_direction"] = _metadata_value("direction", self.direction)
        if self.coordinate_system is not None:
            info["palace_lumped_port_coordinate_system"] = _metadata_value(
                "coordinate_system",
                self.coordinate_system,
            )
        _add_optional_positive(info, "palace_lumped_port_l", self.L)
        _add_optional_positive(info, "palace_lumped_port_c", self.C)
        _add_optional_positive(info, "palace_lumped_port_r", self.R)
        _add_optional_positive(info, "palace_lumped_port_ls", self.Ls)
        _add_optional_positive(info, "palace_lumped_port_cs", self.Cs)
        _add_optional_positive(info, "palace_lumped_port_rs", self.Rs)
        if self.excitation is not None:
            info["palace_lumped_port_excitation"] = self.excitation
        if self.active is not None:
            info["palace_lumped_port_active"] = self.active
        return info

    def to_dict(self) -> dict[str, MetaData]:
        """Return ``to_info()`` for callers that prefer dictionary naming.

        Use when existing cells still call ``to_dict`` while writing the same
        Palace defaults into ``port.info``.

        Example:
            port.info.update(PalaceLumpedPort(R=50.0).to_dict())
        """

        return self.to_info()


SIMULATION_PORT_TYPES: Final[tuple[str, ...]] = tuple(
    str(port_type) for port_type in SimulationPortType
)


def _metadata_value(name: str, value: StrEnum | str) -> str:
    serialized = value.value if isinstance(value, StrEnum) else str(value)
    if not serialized:
        raise ValueError(f"{name} must not be empty.")
    return serialized


def _validate_positive(name: str, value: float) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be positive when provided.")


def _add_optional_positive(info: dict[str, MetaData], name: str, value: float | None) -> None:
    if value is None:
        return
    _validate_positive(name, value)
    info[name] = value


def register_sim_port_types() -> None:
    """Register repository simulation port types with GDSFactory.

    Use from PDK setup so GDSFactory accepts ``SimulationPortType`` values such
    as ``sim_mesh`` or ``sim_junction_lumped`` without warning. Component code
    should not call this directly; ``orpen_sc_pdk.pdk.get_pdk()`` already does.

    Example:
        from orpen_sc_pdk.pdk import get_pdk

        pdk = get_pdk()
    """

    import gdsfactory as gf

    for port_type in SIMULATION_PORT_TYPES:
        if port_type not in gf.CONF.port_types:
            if hasattr(gf.CONF.port_types, "append"):
                gf.CONF.port_types.append(port_type)
            else:
                gf.CONF.port_types += (port_type,)


__all__ = [
    "SIMULATION_PORT_TYPES",
    "AxisDirection",
    "CoordinateSystem",
    "MeshPortInfo",
    "MeshProfile",
    "PalaceLumpedPort",
    "Q2dConductorPortInfo",
    "Q2dConductorType",
    "SimulationPortType",
    "register_sim_port_types",
]
