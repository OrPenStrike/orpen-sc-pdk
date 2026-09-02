#!/usr/bin/env python3
"""Generate or verify derived IPYNB files for canonical QMD notebooks."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any


class NotebookPairError(RuntimeError):
    """Raised when a canonical QMD and its derived notebook disagree."""


_PYTHON_FENCE = re.compile(r"^```\{python(?:\s+[^}]*)?\}\s*$")
_CELL_ID = re.compile(r"^#\|\s*id:\s*['\"]?([A-Za-z0-9_-]{1,64})['\"]?\s*$")


def _require_explicit_code_ids(source: Path) -> None:
    lines = source.read_text(encoding="utf-8").splitlines()
    in_python = False
    code_cell = 0
    for line_number, line in enumerate(lines, start=1):
        if not in_python and _PYTHON_FENCE.match(line):
            in_python = True
            code_cell += 1
            continue
        if not in_python:
            continue
        if line == "```":
            raise NotebookPairError(
                f"{source}: Python cell {code_cell} has no explicit '#| id:' option"
            )
        if not line.strip():
            continue
        if not _CELL_ID.match(line):
            raise NotebookPairError(
                f"{source}:{line_number}: Python cell {code_cell} must begin with '#| id:'"
            )
        in_python = False


def _render_qmd(source: Path, quarto: str) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile(
        dir=source.parent,
        prefix=f".{source.stem}.pair-check-",
        suffix=".qmd",
        delete=False,
    ) as staged:
        staged.write(source.read_bytes())
        staged_source = Path(staged.name)

    command = [
        quarto,
        "render",
        str(staged_source),
        "--to",
        "ipynb",
        "--no-execute",
        "--no-clean",
        "--output",
        "-",
    ]
    try:
        completed = subprocess.run(command, check=True, capture_output=True)
    except FileNotFoundError as exc:
        raise NotebookPairError(f"Quarto executable not found: {quarto}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout).decode("utf-8", errors="replace").strip()
        raise NotebookPairError(f"Quarto failed for {source}: {detail}") from exc
    finally:
        staged_source.unlink(missing_ok=True)

    try:
        notebook = json.loads(completed.stdout)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NotebookPairError(f"Quarto returned invalid IPYNB JSON for {source}: {exc}") from exc
    if not isinstance(notebook, dict) or not isinstance(notebook.get("cells"), list):
        raise NotebookPairError(f"Quarto returned an invalid notebook for {source}")
    return notebook


def _canonicalize_ids(notebook: dict[str, Any], label: str) -> None:
    seen: set[str] = set()
    markdown_index = 0
    raw_index = 0
    for index, cell in enumerate(notebook["cells"]):
        if not isinstance(cell, dict):
            raise NotebookPairError(f"{label}: cell {index} is not an object")
        cell_type = cell.get("cell_type")
        if cell_type == "markdown":
            cell_id = f"markdown-{markdown_index:03d}"
            markdown_index += 1
            cell["id"] = cell_id
        elif cell_type == "raw":
            cell_id = f"raw-{raw_index:03d}"
            raw_index += 1
            cell["id"] = cell_id
        elif cell_type == "code":
            cell_id = cell.get("id")
            if not isinstance(cell_id, str) or not cell_id:
                raise NotebookPairError(f"{label}: code cell {index} has no stable id")
            if cell.get("execution_count") is not None or cell.get("outputs", []) != []:
                raise NotebookPairError(f"{label}: fresh QMD render unexpectedly contains outputs")
        else:
            raise NotebookPairError(f"{label}: unsupported cell type {cell_type!r}")
        if cell_id in seen:
            raise NotebookPairError(f"{label}: duplicate cell id {cell_id!r}")
        seen.add(cell_id)


def _source_text(value: Any, label: str) -> str:
    if isinstance(value, str):
        return value.replace("\r\n", "\n")
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return "".join(value).replace("\r\n", "\n")
    raise NotebookPairError(f"{label}: cell source must be text")


def _normalized_inputs(notebook: dict[str, Any], label: str) -> dict[str, Any]:
    if notebook.get("nbformat") != 4:
        raise NotebookPairError(f"{label}: expected nbformat 4")
    cells = notebook.get("cells")
    if not isinstance(cells, list) or not cells:
        raise NotebookPairError(f"{label}: notebook must contain cells")

    seen: set[str] = set()
    normalized_cells: list[dict[str, Any]] = []
    for index, cell in enumerate(cells):
        if not isinstance(cell, dict):
            raise NotebookPairError(f"{label}: cell {index} is not an object")
        cell_id = cell.get("id")
        if not isinstance(cell_id, str) or not cell_id:
            raise NotebookPairError(f"{label}: cell {index} has no stable id")
        if cell_id in seen:
            raise NotebookPairError(f"{label}: duplicate cell id {cell_id!r}")
        seen.add(cell_id)
        cell_type = cell.get("cell_type")
        if cell_type not in {"markdown", "code", "raw"}:
            raise NotebookPairError(f"{label}: unsupported cell type {cell_type!r}")
        metadata = cell.get("metadata", {})
        if not isinstance(metadata, dict):
            raise NotebookPairError(f"{label}: cell {cell_id!r} metadata is not an object")
        normalized_cell = dict(cell)
        normalized_cell.pop("execution_count", None)
        normalized_cell.pop("outputs", None)
        normalized_cell["source"] = _source_text(cell.get("source", ""), label)
        normalized_cells.append(normalized_cell)

    metadata = notebook.get("metadata", {})
    if not isinstance(metadata, dict):
        raise NotebookPairError(f"{label}: notebook metadata is not an object")
    normalized_notebook = dict(notebook)
    normalized_notebook["cells"] = normalized_cells
    return normalized_notebook


def _load_notebook(path: Path) -> dict[str, Any]:
    try:
        notebook = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NotebookPairError(f"cannot read derived notebook {path}: {exc}") from exc
    if not isinstance(notebook, dict):
        raise NotebookPairError(f"derived notebook {path} must be a JSON object")
    return notebook


def _write_notebook(path: Path, notebook: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = (json.dumps(notebook, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as tmp:
        tmp.write(rendered)
        staged = Path(tmp.name)
    staged.replace(path)


def _pair_path(source: Path, source_root: Path, output_root: Path) -> Path:
    return output_root / source.relative_to(source_root).with_suffix(".ipynb")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_root", type=Path)
    parser.add_argument("output_root", type=Path)
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--quarto", default="quarto")
    args = parser.parse_args()

    source_root = args.source_root.resolve()
    output_root = args.output_root.resolve()
    sources = sorted(source_root.rglob("*.qmd"))
    if not sources:
        raise NotebookPairError(f"no canonical QMD notebooks found under {source_root}")

    for source in sources:
        _require_explicit_code_ids(source)
        expected = _render_qmd(source, args.quarto)
        _canonicalize_ids(expected, str(source))
        derived = _pair_path(source, source_root, output_root)
        if args.generate:
            _write_notebook(derived, expected)
        elif not derived.is_file():
            raise NotebookPairError(f"derived notebook is missing: {derived}")

        actual = _load_notebook(derived)
        expected_inputs = _normalized_inputs(expected, f"fresh render of {source}")
        actual_inputs = _normalized_inputs(actual, str(derived))
        if actual_inputs != expected_inputs:
            raise NotebookPairError(
                f"{derived} input structure drifted from canonical source {source}"
            )
        action = "generated" if args.generate else "verified"
        print(f"PASS: {action} {derived.relative_to(output_root)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except NotebookPairError as exc:
        raise SystemExit(f"FAIL: {exc}") from exc
