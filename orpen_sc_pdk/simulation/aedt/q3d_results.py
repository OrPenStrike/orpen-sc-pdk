"""Path-based Q3D Maxwell capacitance result display."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class Q3dCapacitanceResult:
    """One Q3D Maxwell matrix, optional three-node branches, and timings."""

    maxwell: pd.DataFrame
    derived: pd.DataFrame
    unit: str
    timings: pd.DataFrame

    def show(self) -> None:
        """Display the Maxwell matrix, derived branches, and timing records."""

        from IPython.display import display

        display(self.maxwell)
        display(self.derived)
        display(self.timings)


def load_q3d_capacitance_result(
    matrix_path: str | Path,
    *,
    node_labels: Sequence[str],
    result_path: str | Path | None = None,
) -> Q3dCapacitanceResult:
    """Load a Maxwell capacitance matrix for the requested Q3D node labels."""

    labels = tuple(node_labels)
    maxwell, unit = _load_maxwell_matrix(Path(matrix_path), len(labels))
    if (
        len(labels) != len(set(labels))
        or set(maxwell.index) != set(labels)
        or set(maxwell.columns) != set(labels)
    ):
        raise RuntimeError(f"Q3D Maxwell matrix nodes do not match {labels!r}")
    maxwell = maxwell.loc[labels, labels]
    if not maxwell.map(math.isfinite).all().all():
        raise RuntimeError("Q3D Maxwell matrix contains a non-finite value.")
    derived = pd.DataFrame()
    if len(labels) == 3:
        reference, node_1, node_2 = labels
        derived = pd.DataFrame(
            {
                "branch": (f"{node_1}-{reference}", f"{node_2}-{reference}", f"{node_1}-{node_2}"),
                "value": (
                    -maxwell.loc[node_1, reference],
                    -maxwell.loc[node_2, reference],
                    -maxwell.loc[node_1, node_2],
                ),
                "unit": unit,
            }
        )
    return Q3dCapacitanceResult(
        maxwell=maxwell,
        derived=derived,
        unit=unit,
        timings=_load_timings(Path(result_path)) if result_path is not None else pd.DataFrame(),
    )


def _load_maxwell_matrix(path: Path, size: int) -> tuple[pd.DataFrame, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    try:
        table_index = lines.index("Capacitance Matrix")
        units_line = next(line for line in lines if "C Units:" in line)
    except (StopIteration, ValueError) as exc:
        raise RuntimeError(f"Q3D capacitance export is invalid: {path}") from exc
    unit_match = re.search(r"C Units:([^,]+)", units_line)
    if unit_match is None:
        raise RuntimeError(f"Q3D capacitance export has no capacitance unit: {path}")
    matrix = pd.read_csv(StringIO("\n".join(lines[table_index + 1 :])), index_col=0, nrows=size)
    matrix = matrix.loc[:, ~matrix.columns.str.startswith("Unnamed:")]
    matrix.index = matrix.index.astype(str).str.strip()
    matrix.columns = matrix.columns.astype(str).str.strip()
    return matrix.apply(pd.to_numeric, errors="raise"), unit_match.group(1).strip()


def _load_timings(path: Path) -> pd.DataFrame:
    payload = json.loads(path.read_text(encoding="utf-8"))
    timings = payload.get("stage_timing", payload)
    if isinstance(timings, dict):
        return pd.DataFrame(timings.items(), columns=("stage", "elapsed_seconds"))
    if isinstance(timings, list):
        return pd.DataFrame(timings)
    raise RuntimeError(f"Q3D timing result is invalid: {path}")


__all__ = ["Q3dCapacitanceResult", "load_q3d_capacitance_result"]
