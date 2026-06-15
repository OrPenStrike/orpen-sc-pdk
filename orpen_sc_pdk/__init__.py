"""OrPen superconducting quantum/RF public PDK."""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from functools import lru_cache, partial

from gdsfactory.typings import ComponentFactory

from . import cells, config, materials, tech
from .config import PATH
from .materials import (
    get_gsim_dielectric_interface_preset_kwargs,
    get_gsim_material_kind_alias_map,
    get_gsim_material_kind_map,
    get_gsim_material_overlay,
    get_interface_preset_records,
    get_material_alias_records,
    get_material_records,
    validate_interface_preset_records,
    validate_material_alias_records,
    validate_material_kind_records,
    write_gsim_material_overlay,
)
from .pdk import PDK, activate, get_pdk
from .tech import LAYER, LAYER_CONNECTIVITY, LAYER_STACK, LAYER_VIEWS


@lru_cache(maxsize=1)
def get_sample_functions() -> dict[str, ComponentFactory]:
    """Return bundled public sample factories by function name."""

    import orpen_sc_pdk.samples as sample_package

    samples: dict[str, ComponentFactory] = {}
    for _importer, module_name, _is_package in pkgutil.walk_packages(
        sample_package.__path__,
        sample_package.__name__ + ".",
    ):
        module = importlib.import_module(module_name)
        public_names = getattr(module, "__all__", None)
        members = (
            ((name, getattr(module, name)) for name in public_names)
            if public_names is not None
            else inspect.getmembers(module)
        )
        for name, obj in members:
            if name.startswith("_"):
                continue
            if not (inspect.isfunction(obj) or isinstance(obj, partial)):
                continue
            if public_names is None and getattr(obj, "func", obj).__module__ != module_name:
                continue
            samples[f"{module_name}.{name}"] = obj
    return samples


__all__ = [
    "LAYER",
    "LAYER_CONNECTIVITY",
    "LAYER_STACK",
    "LAYER_VIEWS",
    "PATH",
    "PDK",
    "activate",
    "cells",
    "config",
    "get_gsim_dielectric_interface_preset_kwargs",
    "get_gsim_material_kind_alias_map",
    "get_gsim_material_kind_map",
    "get_sample_functions",
    "get_pdk",
    "get_gsim_material_overlay",
    "get_interface_preset_records",
    "get_material_alias_records",
    "get_material_records",
    "materials",
    "tech",
    "validate_material_alias_records",
    "validate_material_kind_records",
    "validate_interface_preset_records",
    "write_gsim_material_overlay",
]

__version__ = "0.1.0"
