from __future__ import annotations

import pytest

from orpen_sc_pdk.simulation.aedt import Axis, ParameterSpace


def test_axis_defaulting_and_validation() -> None:
    axis = Axis(name="width", values=(1.0, 2.0, 3.0))
    assert axis.default == 1.0

    with pytest.raises(ValueError, match="values cannot be empty"):
        Axis(name="empty", values=())

    with pytest.raises(ValueError, match="Python keyword-argument name"):
        Axis(name="bad-name", values=(1,))

    with pytest.raises(ValueError, match="default .* is not in values"):
        Axis(name="bad", values=(1, 2), default=3)


def test_parameter_space_unique_axis_names() -> None:
    with pytest.raises(ValueError, match="axis names must be unique"):
        ParameterSpace(Axis("w", (1, 2)), Axis("w", (3, 4)))


def test_point_defaults_membership_and_id() -> None:
    space = ParameterSpace(
        Axis("w", (1.0, 2.0)),
        Axis("g", (6, 8), default=8),
        Axis("label", ("a/b", "b c")),
    )

    point = space.point()
    assert point.coords == {"w": 1.0, "g": 8, "label": "a/b"}
    assert point.id == "w=1.0__g=8__label=a-b"

    with pytest.raises(ValueError, match="unknown axis"):
        space.point(z=1)
    with pytest.raises(ValueError, match="does not include value"):
        space.point(g=9)


def test_grid_line_plane_slice_contract() -> None:
    space = ParameterSpace(Axis("a", (1, 2)), Axis("b", ("x", "y")), Axis("c", ("L", "R")))

    assert [p.id for p in space.grid()] == [
        "a=1__b=x__c=L",
        "a=1__b=x__c=R",
        "a=1__b=y__c=L",
        "a=1__b=y__c=R",
        "a=2__b=x__c=L",
        "a=2__b=x__c=R",
        "a=2__b=y__c=L",
        "a=2__b=y__c=R",
    ]

    assert [p.coords["a"] for p in space.line("a", c="R")] == [1, 2]

    assert [p.id for p in space.plane("a", "b")] == [
        "a=1__b=x__c=L",
        "a=1__b=y__c=L",
        "a=2__b=x__c=L",
        "a=2__b=y__c=L",
    ]

    assert [p.id for p in space.slice(("c",), a=2)] == [
        "a=2__b=x__c=L",
        "a=2__b=x__c=R",
    ]

    assert [p.id for p in space.slice("c", a=2)] == [
        "a=2__b=x__c=L",
        "a=2__b=x__c=R",
    ]
