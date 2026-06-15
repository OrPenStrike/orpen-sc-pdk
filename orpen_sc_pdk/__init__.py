"""OrPen superconducting quantum/RF public PDK."""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from functools import lru_cache, partial

from gdsfactory.typings import ComponentFactory

from . import cells, config, helper, materials, models, tech
from .config import PATH
from .logger import logger
from .materials import (
    get_gsim_dielectric_interface_preset_kwargs,
    get_gsim_material_overlay,
    get_interface_preset_records,
    get_material_records,
    validate_interface_preset_records,
    write_gsim_material_overlay,
)
from .pdk import PDK, activate, get_pdk
from .tech import LAYER, LAYER_CONNECTIVITY, LAYER_STACK, LAYER_VIEWS


@lru_cache(maxsize=1)
def get_sample_functions() -> dict[str, ComponentFactory]:
    """Return bundled public sample factories by function name."""

    import orpen_sc_pdk.samples as sample_package

    return {
        f"{module_name}.{name}": obj
        for _importer, module_name, _is_package in pkgutil.walk_packages(
            sample_package.__path__,
            sample_package.__name__ + ".",
        )
        for name, obj in inspect.getmembers(importlib.import_module(module_name))
        if (inspect.isfunction(obj) or isinstance(obj, partial))
        and not name.startswith("_")
        and getattr(obj, "func", obj).__module__ == module_name
    }


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
    "get_sample_functions",
    "get_pdk",
    "helper",
    "get_gsim_material_overlay",
    "get_interface_preset_records",
    "get_material_records",
    "logger",
    "materials",
    "models",
    "tech",
    "validate_interface_preset_records",
    "write_gsim_material_overlay",
]

__version__ = "0.1.0"
