from __future__ import annotations

import ast
from pathlib import Path

NOTEBOOK_SOURCE_DIR = Path("notebooks/src")
QUICKSTART_NOTEBOOK = NOTEBOOK_SOURCE_DIR / "public_pdk_quickstart.py"
INVENTORY_NOTEBOOK = NOTEBOOK_SOURCE_DIR / "public_simulation_inventory.py"
PROBLEM_NOTEBOOKS = (
    NOTEBOOK_SOURCE_DIR / "public_driven_workflow.py",
    NOTEBOOK_SOURCE_DIR / "public_eigenmode_workflow.py",
    NOTEBOOK_SOURCE_DIR / "public_electrostatic_workflow.py",
)
PUBLIC_NOTEBOOKS = (QUICKSTART_NOTEBOOK, *PROBLEM_NOTEBOOKS, INVENTORY_NOTEBOOK)


def _is_private_name(name: str) -> bool:
    return any(part.startswith("_") and not part.startswith("__") for part in name.split("."))


def test_public_problem_type_notebooks_are_split() -> None:
    assert not (NOTEBOOK_SOURCE_DIR / "public_simulation_workflows.py").exists()
    for notebook in PROBLEM_NOTEBOOKS:
        assert notebook.exists()


def test_public_notebook_sources_exist() -> None:
    for notebook in PUBLIC_NOTEBOOKS:
        assert notebook.exists()


def test_public_notebook_index_does_not_link_combined_simulation_workflow() -> None:
    assert "public_simulation_workflows" not in Path("docs/notebooks.rst").read_text()


def test_public_notebooks_do_not_define_local_functions() -> None:
    for notebook in PUBLIC_NOTEBOOKS:
        tree = ast.parse(notebook.read_text(), filename=str(notebook))
        definitions = [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        ]
        assert definitions == []


def test_public_notebooks_do_not_reference_private_symbols() -> None:
    for notebook in PUBLIC_NOTEBOOKS:
        tree = ast.parse(notebook.read_text(), filename=str(notebook))
        private_symbols = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                private_symbols.extend(
                    alias.asname or alias.name
                    for alias in node.names
                    if _is_private_name(alias.name)
                    or (alias.asname is not None and _is_private_name(alias.asname))
                )
            elif isinstance(node, ast.ImportFrom):
                private_symbols.extend(
                    alias.asname or alias.name
                    for alias in node.names
                    if _is_private_name(alias.name)
                    or (alias.asname is not None and _is_private_name(alias.asname))
                )
            elif isinstance(node, ast.Name) and _is_private_name(node.id):
                private_symbols.append(node.id)
            elif isinstance(node, ast.Attribute) and _is_private_name(node.attr):
                private_symbols.append(node.attr)
        assert private_symbols == []
