from __future__ import annotations

import ast
from pathlib import Path

NOTEBOOK_SOURCE_DIR = Path("notebooks/src")
PROBLEM_NOTEBOOKS = (
    NOTEBOOK_SOURCE_DIR / "public_driven_workflow.py",
    NOTEBOOK_SOURCE_DIR / "public_eigenmode_workflow.py",
    NOTEBOOK_SOURCE_DIR / "public_electrostatic_workflow.py",
)


def test_public_problem_type_notebooks_are_split() -> None:
    assert not (NOTEBOOK_SOURCE_DIR / "public_simulation_workflows.py").exists()
    for notebook in PROBLEM_NOTEBOOKS:
        assert notebook.exists()


def test_public_problem_type_notebooks_do_not_define_local_functions() -> None:
    for notebook in PROBLEM_NOTEBOOKS:
        tree = ast.parse(notebook.read_text(), filename=str(notebook))
        definitions = [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        ]
        assert definitions == []


def test_public_problem_type_notebooks_do_not_call_private_helpers() -> None:
    for notebook in PROBLEM_NOTEBOOKS:
        tree = ast.parse(notebook.read_text(), filename=str(notebook))
        private_calls = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            else:
                continue
            if name.startswith("_") and not name.startswith("__"):
                private_calls.append(name)
        assert private_calls == []
