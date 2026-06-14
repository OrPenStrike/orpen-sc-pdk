from __future__ import annotations

import textwrap

from orpen_sc_pdk.cells._private_mount import load_private_cells, load_private_cross_sections


def test_private_mount_missing_source_is_noop(tmp_path) -> None:
    namespace = {}

    assert load_private_cells(namespace, mount_root=tmp_path) == ()
    assert namespace == {}
    assert load_private_cross_sections(mount_root=tmp_path) == {}


def test_private_mount_loads_cells_and_cross_sections(tmp_path) -> None:
    package_root = tmp_path / "fake-private-layouts" / "src" / "fake_private_layouts"
    package_root.mkdir(parents=True)
    (package_root / "__init__.py").write_text("", encoding="utf-8")
    (package_root / "cells.py").write_text(
        textwrap.dedent(
            """
            import gdsfactory as gf

            @gf.cell
            def fake_private_cell() -> gf.Component:
                return gf.Component()

            __all__ = ["fake_private_cell"]
            """
        ),
        encoding="utf-8",
    )
    (package_root / "xsections.py").write_text(
        textwrap.dedent(
            """
            import gdsfactory as gf
            from gdsfactory.cross_section import xsection

            @xsection
            def fake_private_xs():
                return gf.cross_section.cross_section(width=1.0, layer=(1, 0))
            """
        ),
        encoding="utf-8",
    )

    namespace = {}
    cell_names = load_private_cells(
        namespace,
        mount_root=tmp_path,
        repo_name="fake-private-layouts",
        cells_package="fake_private_layouts.cells",
    )
    cross_sections = load_private_cross_sections(
        mount_root=tmp_path,
        repo_name="fake-private-layouts",
        xsections_package="fake_private_layouts.xsections",
    )

    assert cell_names == ("fake_private_cell",)
    assert namespace["fake_private_cell"]().name.startswith("fake_private_cell")
    assert "fake_private_xs" in cross_sections
