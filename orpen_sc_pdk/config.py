"""Repository path configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path as _Path


@dataclass(frozen=True)
class Path:
    """Common package and repository paths."""

    module: _Path = _Path(__file__).resolve().parent
    repo: _Path = module.parent
    build: _Path = repo / "build"
    docs: _Path = repo / "docs"
    gds: _Path = build / "gds"
    simulation: _Path = build / "simulation"
    tests: _Path = repo / "tests"
    cells: _Path = module / "cells"
    klayout: _Path = module / "klayout"
    models: _Path = module / "models"
    samples: _Path = module / "samples"
    lyp: _Path = klayout / "layers.lyp"
    lyt: _Path = klayout / "tech.lyt"
    lyp_yaml: _Path = module / "layers.yaml"
    tech: _Path = klayout / "tech"


PATH = Path()
