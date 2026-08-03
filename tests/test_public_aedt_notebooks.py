from __future__ import annotations

import importlib
import json
import math
import types
from pathlib import Path

import pytest


def test_q2d_semantic_notebook_uses_palace_style_aedt_run_root() -> None:
    notebook_path = Path(
        "notebooks/AEDTSimulation/Components/CPW Cross Section Q2D Flip Chip Two Trace Zo Zm.ipynb"
    )
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    source = "\n".join("".join(cell.get("source", ())) for cell in notebook["cells"])

    assert 'SIMULATION_PURPOSE_ID = "q2d_cpw_flip_chip_two_trace_zo_zm"' in source
    assert 'AEDT_WORK_DIR = PATH.simulation / "aedt" / SIMULATION_PURPOSE_ID' in source
    assert "AEDT_RUN_ROOT = AEDT_WORK_DIR / NOTEBOOK_RUN_ID" in source
    assert "AEDT_PACKAGE_DIR = AEDT_RUN_ROOT" in source
    assert (
        'AEDT_ARCHIVE_PATH = AEDT_RUN_ROOT.parent / f"{AEDT_RUN_ROOT.name}-aedt.tar.gz"' in source
    )
    assert "AEDT_MEMORY_MB_TOTAL = 240000" in source
    assert "memory_mb_total=AEDT_MEMORY_MB_TOTAL" in source
    assert "TemporaryDirectory()" in source
    assert 'AEDT_WORK_DIR / "cross_sections"' not in source
    assert 'AEDT_PACKAGE_DIR = AEDT_WORK_DIR / "aedt_native"' not in source


def test_q2d_semantic_cross_section_payload_contract(tmp_path: Path) -> None:
    from orpen_sc_pdk.simulation.aedt import (
        Air,
        Die,
        DieGap,
        FacePattern,
        Gap,
        Ground,
        Q2dSemanticCrossSection,
        Stack,
        Trace,
        validate_q2d_cross_section_payload,
        write_q2d_cross_section_payload,
    )

    cross_section = Q2dSemanticCrossSection(
        stack=Stack(
            (
                Air(height_um=100),
                Die(id="D0", thickness_um=500, material="Silicon"),
                DieGap(height_um=8),
                Die(id="D1", thickness_um=500, material="Silicon"),
                Air(height_um=100),
            )
        ),
        face_patterns=(
            FacePattern(
                die="D0",
                face="top",
                metal_thickness_um=0.2,
                segments=(
                    Ground(width_um=50),
                    Gap(width_um=6),
                    Trace("T1", width_um=7),
                    Gap(width_um=6),
                    Ground(width_um=8),
                    Gap(width_um=6),
                    Trace("T2", width_um=7),
                    Gap(width_um=6),
                    Ground(width_um=50),
                ),
            ),
        ),
    )

    path = write_q2d_cross_section_payload(tmp_path / "q2d_cross_section.json", cross_section)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert validate_q2d_cross_section_payload(payload) == payload
    assert payload["stack"][0]["kind"] == "air"
    assert payload["stack"][1]["kind"] == "die"
    assert payload["stack"][2]["kind"] == "die_gap"
    assert payload["face_patterns"][0]["segments"][4] == {"kind": "ground", "width_um": 8}


def test_q2d_same_face_upper_ground_clearance_contract() -> None:
    from orpen_sc_pdk.simulation.aedt.q2d import (
        make_q2d_same_face_two_trace_cross_section,
        validate_q2d_same_face_upper_ground_clearance_payload,
    )

    cross_section = make_q2d_same_face_two_trace_cross_section(
        trace_width_um=8.0,
        trace_gap_um=6.0,
        inter_trace_ground_width_um=4.0,
        upper_ground_clearance_width_um=40.0,
        flip_chip_gap_height_um=10.0,
        die_thickness_um=100.0,
        air_height_um=50.0,
        ground_width_um=30.0,
        metal_thickness_um=0.2,
    )
    payload = cross_section.to_payload()
    summary = validate_q2d_same_face_upper_ground_clearance_payload(payload)

    assert [element["id"] for element in payload["stack"] if element["kind"] == "die"] == [
        "D0",
        "D1",
    ]
    trace_locations = {
        segment["name"]: (pattern["die"], pattern["face"])
        for pattern in payload["face_patterns"]
        for segment in pattern["segments"]
        if segment["kind"] == "trace"
    }
    assert trace_locations == {"T1": ("D0", "top"), "T2": ("D0", "top")}
    d1_pattern = next(
        pattern
        for pattern in payload["face_patterns"]
        if pattern["die"] == "D1" and pattern["face"] == "bottom"
    )
    assert [segment["kind"] for segment in d1_pattern["segments"]] == [
        "ground",
        "gap",
        "ground",
    ]
    assert d1_pattern["segments"][1] == {
        "kind": "gap",
        "role": "upper_ground_clearance",
        "width_um": 40.0,
    }
    assert summary == {
        "schema_version": "q2d-same-face-upper-ground-clearance.v1",
        "resonator_die": "D0",
        "resonator_face": "top",
        "trace_names": ["T1", "T2"],
        "upper_die": "D1",
        "upper_die_substrate_present": True,
        "upper_ground_face": "bottom",
        "upper_ground_clearance_width_um": 40.0,
        "upper_ground_metal_policy": "removed_only_within_local_clearance",
        "reference_group": "Ground",
    }

    with pytest.raises(ValueError, match="leave positive D1 ground metal"):
        make_q2d_same_face_two_trace_cross_section(
            trace_width_um=8.0,
            trace_gap_um=6.0,
            inter_trace_ground_width_um=4.0,
            upper_ground_clearance_width_um=104.0,
            flip_chip_gap_height_um=10.0,
            die_thickness_um=100.0,
            air_height_um=50.0,
            ground_width_um=30.0,
            metal_thickness_um=0.2,
        )


def test_q2d_semantic_cross_section_rejects_air_inside_stack() -> None:
    from orpen_sc_pdk.simulation.aedt import Air, Die, Q2dSemanticCrossSection, Stack

    with pytest.raises(ValueError, match="Air is only allowed at stack edges"):
        Q2dSemanticCrossSection(
            stack=Stack(
                (
                    Die(id="D0", thickness_um=500, material="Silicon"),
                    Air(height_um=100),
                    Die(id="D1", thickness_um=500, material="Silicon"),
                )
            ),
            face_patterns=(),
        )


def test_q2d_raw_and_derived_result_api(tmp_path: Path) -> None:
    from orpen_sc_pdk.simulation.aedt import (
        Axis,
        ParameterSpace,
        Q2dImpedanceFormula,
        Q2dMatrixElement,
        load_q2d_raw_sweep_result,
    )

    parameter_space = ParameterSpace(
        Axis("x", (0.0, 1.0)),
        Axis("y", (2.0,)),
    )
    run_root = tmp_path / "aedt_run"

    def _write_matrix(
        path: Path,
        *,
        problem_type: str,
        unit_line: str,
        title: str,
        t1_t1: float,
        t1_t2: float,
        t2_t1: float,
        t2_t2: float,
    ) -> None:
        path.write_text(
            "\n".join(
                [
                    "Setup1 : LastAdaptive",
                    f"Problem Type: {problem_type}",
                    "Reduce Matrix: Original",
                    "Frequency: 6GHz",
                    unit_line,
                    title,
                    ",T1,T2",
                    f"T1,{t1_t1},{t1_t2}",
                    f"T2,{t2_t1},{t2_t2}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    for point in parameter_space.grid():
        point_slug = point.id.replace("=", "_")
        point_dir = run_root / "points" / point_slug / "q2d"
        point_dir.mkdir(parents=True)
        scale = 1.0 if point.coords["x"] == 0.0 else 2.0
        _write_matrix(
            point_dir / "cg_maxwell_matrix.csv",
            problem_type="CG",
            unit_line="C Units:pF/meter",
            title="Capacitance Matrix",
            t1_t1=100.0 * scale,
            t1_t2=-20.0 * scale,
            t2_t1=-20.0 * scale,
            t2_t2=110.0 * scale,
        )
        _write_matrix(
            point_dir / "rl_maxwell_matrix.csv",
            problem_type="RL",
            unit_line="L Units:nH/meter",
            title="Inductance Matrix",
            t1_t1=400.0 * scale,
            t1_t2=80.0 * scale,
            t2_t1=80.0 * scale,
            t2_t2=420.0 * scale,
        )
        _write_matrix(
            point_dir / "cg_couple_matrix.csv",
            problem_type="CG",
            unit_line="C Units:1",
            title="Capacitance Matrix Coupling Coefficient",
            t1_t1=1.0,
            t1_t2=-0.2,
            t2_t1=-0.2,
            t2_t2=1.0,
        )
        _write_matrix(
            point_dir / "rl_couple_matrix.csv",
            problem_type="RL",
            unit_line="L Units:1",
            title="Inductance Matrix Coupling Coefficient",
            t1_t1=1.0,
            t1_t2=0.15,
            t2_t1=0.15,
            t2_t2=1.0,
        )

    result = load_q2d_raw_sweep_result(run_root, parameter_space, recipe_id="q2d")
    assert tuple(sorted(result.available_terminals())) == ("T1", "T2")
    raw_point = result.point(x=0.0)
    assert raw_point.matrix_table()
    assert raw_point.value(Q2dMatrixElement("cg_couple", "C", "T1", "T2")) == pytest.approx(-0.2)
    assert [point.point_slug for point in result.line("x")] == [
        point.id.replace("=", "_") for point in parameter_space.line("x")
    ]
    raw_csv = result.write_csv()

    derived = result.derive(
        Q2dImpedanceFormula.self(name="zo", trace_names=("T1", "T2")),
        Q2dImpedanceFormula.mutual(name="zm", trace_pair=("T1", "T2")),
    )
    assert [row["point_slug"] for row in derived.rows] == [
        point.id.replace("=", "_") for point in parameter_space.grid()
    ]
    assert derived.rows[0]["zo_T1_ohm"] == pytest.approx(math.sqrt(400e-9 / 100e-12))
    assert derived.rows[0]["zo_T2_ohm"] == pytest.approx(math.sqrt(420e-9 / 110e-12))
    assert derived.rows[0]["zm_T1_T2_ohm"] == pytest.approx(math.sqrt(80e-9 / (20e-12)))

    derived_csv = derived.write_csv()
    manifest_path = derived.write_formula_manifest()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    formula_names = [formula["name"] for formula in manifest["formulas"]]
    assert formula_names == ["zo", "zm"]
    assert manifest["formulas"][1]["parameters"]["capacitance_scale"] == -1

    assert raw_csv.is_file()
    assert derived_csv.is_file()

    view = derived.slice(("x", "y"))
    assert view.show_all_results()["axes"] == ["x", "y"]
    assert view.show_all_results()["rows"] == len(derived.rows)
    line_view = derived.line("x")
    assert line_view.metrics == ("zo_T1_ohm", "zo_T2_ohm", "zm_T1_T2_ohm")
    filtered = line_view.where(
        x=lambda value: value >= 1.0,
        y=2.0,
        point_slug=(line_view.rows[-1]["point_slug"],),
    )
    assert [row["x"] for row in filtered.rows] == [1.0]
    assert filtered.axes == line_view.axes
    assert filtered.formulas == line_view.formulas
    view_csv = line_view.write_csv()
    assert view_csv.is_file()
    assert view_csv != derived_csv
    assert view_csv.name.startswith("q2d_derived_view__x__y_2.0")

    missing_point = tmp_path / "missing"
    missing_point_dir = missing_point / "points" / "x_0.0__y_2.0" / "q2d"
    missing_point_dir.mkdir(parents=True)
    for filename in ("cg_maxwell_matrix.csv", "rl_maxwell_matrix.csv", "cg_couple_matrix.csv"):
        _write_matrix(
            missing_point_dir / filename,
            problem_type="CG",
            unit_line="C Units:pF/meter",
            title="Capacitance Matrix",
            t1_t1=100.0,
            t1_t2=-20.0,
            t2_t1=-20.0,
            t2_t2=110.0,
        )
    with pytest.raises(FileNotFoundError):
        load_q2d_raw_sweep_result(missing_point, parameter_space, recipe_id="q2d")


def test_q2d_plotly_line_and_heatmap_render(monkeypatch: pytest.MonkeyPatch) -> None:
    from orpen_sc_pdk.simulation.aedt import Q2dHeatMap, Q2dLinePlot, Q2dResultView

    figures = []

    class Figure:
        def __init__(self, data=None):
            self.data = [] if data is None else [data]
            self.layout = {}
            self.shown = False
            figures.append(self)

        def add_trace(self, trace):
            self.data.append(trace)

        def update_layout(self, **kwargs):
            self.layout.update(kwargs)

        def show(self):
            self.shown = True

    class Trace:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    fake_go = types.SimpleNamespace(Figure=Figure, Scatter=Trace, Heatmap=Trace)
    real_import_module = importlib.import_module

    def import_module(name: str):
        return fake_go if name == "plotly.graph_objects" else real_import_module(name)

    monkeypatch.setattr(importlib, "import_module", import_module)
    line_view = Q2dResultView(
        [
            {"x": 0.0, "y1": 1.0, "y2": 2.0},
            {"x": 1.0, "y1": 1.5, "y2": 2.5},
        ],
        axes=("x",),
    )
    Q2dLinePlot(y=("y1", "y2")).render(line_view)
    assert figures[-1].shown
    assert [trace.kwargs["name"] for trace in figures[-1].data] == ["y1", "y2"]

    heat_view = Q2dResultView(
        [
            {"x": 0.0, "y": 0.0, "z": 1.0},
            {"x": 1.0, "y": 0.0, "z": 2.0},
            {"x": 0.0, "y": 1.0, "z": 3.0},
            {"x": 1.0, "y": 1.0, "z": 4.0},
        ],
        axes=("x", "y"),
    )
    Q2dHeatMap(z="z").render(heat_view)
    assert figures[-1].shown
    assert figures[-1].data[0].kwargs["z"] == [[1.0, 2.0], [3.0, 4.0]]


def test_q2d_plotly_missing_dependency_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from orpen_sc_pdk.simulation.aedt import Q2dLinePlot, Q2dResultView

    real_import_module = importlib.import_module

    def import_module(name: str):
        if name == "plotly.graph_objects":
            raise ModuleNotFoundError("No module named 'plotly'", name="plotly")
        return real_import_module(name)

    monkeypatch.setattr(importlib, "import_module", import_module)
    view = Q2dResultView([{"x": 0.0, "z": 1.0}], axes=("x",))

    with pytest.raises(ModuleNotFoundError, match="uv sync --all-extras"):
        Q2dLinePlot(y="z").render(view)


def test_q2d_facet_line_grid_plotly_render(monkeypatch: pytest.MonkeyPatch) -> None:
    from orpen_sc_pdk.simulation.aedt import Q2dFacetLineGrid, Q2dResultView

    figures = []

    class Figure:
        def __init__(self, data=None):
            self.traces = [] if data is None else [(data, None, None)]
            self.layout = {}
            self.xaxes = []
            self.yaxes = []
            self.shown = False
            figures.append(self)

        def add_trace(self, trace, row=None, col=None):
            self.traces.append((trace, row, col))

        def update_layout(self, **kwargs):
            self.layout.update(kwargs)

        def update_xaxes(self, **kwargs):
            self.xaxes.append(kwargs)

        def update_yaxes(self, **kwargs):
            self.yaxes.append(kwargs)

        def show(self):
            self.shown = True

    class Trace:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    def make_subplots(**kwargs):
        figure = Figure()
        figure.subplots = kwargs
        return figure

    fake_go = types.SimpleNamespace(Figure=Figure, Scatter=Trace, Heatmap=Trace)
    fake_subplots = types.SimpleNamespace(make_subplots=make_subplots)
    fake_colors = types.SimpleNamespace(
        sample_colorscale=lambda _name, values: [f"color-{values[0]:.1f}"]
    )
    real_import_module = importlib.import_module

    def import_module(name: str):
        if name == "plotly.graph_objects":
            return fake_go
        if name == "plotly.subplots":
            return fake_subplots
        if name == "plotly.colors":
            return fake_colors
        return real_import_module(name)

    monkeypatch.setattr(importlib, "import_module", import_module)
    rows = [
        {
            "horizontal_offset_um": x,
            "trace_gap_um": gap,
            "central_width_um": width,
            "flip_chip_gap_height_um": height,
            "zo_T1_ohm": x + gap + width + height,
        }
        for gap in (3.0, 4.5)
        for width in (7.0, 8.0)
        for height in (7.0, 7.5)
        for x in (0.0, 3.0)
    ]
    view = Q2dResultView(
        rows,
        axes=(
            "horizontal_offset_um",
            "trace_gap_um",
            "central_width_um",
            "flip_chip_gap_height_um",
        ),
    )

    Q2dFacetLineGrid(
        x="horizontal_offset_um",
        y=(("zo_T1_ohm", "Zo Trace1 (ohm)"),),
        facet_col="trace_gap_um",
        color="central_width_um",
        line_dash="flip_chip_gap_height_um",
        line_dash_map={7.0: "solid", 7.5: "dash"},
        color_title="Central metal width (um)",
    ).render(view)

    figure = figures[-1]
    data_lines = [
        trace
        for trace, _row, _col in figure.traces
        if trace.kwargs.get("mode") == "lines" and trace.kwargs.get("showlegend") is False
    ]
    dash_legend = [
        trace
        for trace, _row, _col in figure.traces
        if trace.kwargs.get("mode") == "lines" and trace.kwargs.get("showlegend") is True
    ]
    assert figure.shown
    assert figure.subplots["rows"] == 1
    assert figure.subplots["cols"] == 2
    assert figure.subplots["horizontal_spacing"] == 0.08
    assert figure.layout["margin"]["r"] == 300
    assert figure.layout["legend"]["orientation"] == "h"
    assert len(data_lines) == 8
    assert {trace.kwargs["line"]["dash"] for trace in dash_legend} == {"solid", "dash"}
