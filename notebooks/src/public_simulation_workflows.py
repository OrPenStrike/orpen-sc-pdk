# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.17.3
# ---

# %% [markdown]
# # Public simulation workflows
#
# This notebook demonstrates publication-safe Palace workflow fixtures for the
# public OrPen SC PDK. It exercises the reusable `gsim` mesh/config/artifact
# handoff for Driven, Eigenmode, Electrostatic, and Magnetostatic problem types without
# importing private layouts, private notebooks, saved private outputs, or
# private run folders.
#
# The geometry cells stop at local mesh/config generation. The report cells use
# synthetic public Palace artifacts to exercise reusable report loaders without
# requiring a local solver during the docs build. A full Palace solve can be run
# from the generated `config.json` and `palace.msh` when a Palace binary is
# available.

# %%
from __future__ import annotations

import json
import os
import tempfile
import warnings
from pathlib import Path

import pandas as pd
from gsim.palace import (
    DrivenSim,
    EigenmodeSim,
    ElectrostaticSim,
    MagnetostaticSim,
    PalaceSlurmSbatchSpec,
    load_dielectric_interface_summary,
    load_domain_material_summary,
    load_driven_report,
    load_eigenmode_report,
    load_electrostatic_report,
    load_palace_run_summary,
    load_palace_slurm_profile_catalog,
    load_postprocessing_index_map,
    resolve_palace_slurm_profile,
    write_palace_slurm_sbatch_handoff,
)
from gsim.palace.mesh import (
    SurfaceFluxSpec,
    build_dielectric_interface_specs_from_material_kinds,
    build_postprocessing_config_from_manifest,
)
from IPython.display import display

import orpen_sc_pdk
from orpen_sc_pdk.cells import (
    cpw_straight,
    martinis2022_differential_ribbon_capacitor,
    resonator,
)
from orpen_sc_pdk.materials import (
    get_gsim_material_kind_alias_map,
    get_gsim_material_kind_map,
    get_gsim_material_overlay,
    validate_interface_preset_records,
)

warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    message="Material model for evaluation at wavelength=.*has unspecified validity range.*",
    module="gsim.palace.materials",
)

orpen_sc_pdk.activate()


def _find_repo_file(relative_path: str) -> Path:
    search_roots = [Path.cwd(), *Path.cwd().parents]
    if "__file__" in globals():
        source_path = Path(__file__).resolve()
        search_roots.extend([source_path.parent, *source_path.parents])
    for root in search_roots:
        candidate = root / relative_path
        if candidate.is_file():
            return candidate
    return Path(relative_path)


PUBLIC_SLURM_PROFILE_CATALOG_REF = "scripts/fixtures/public_slurm_profiles.json"
PUBLIC_SLURM_PROFILE_CATALOG = _find_repo_file(PUBLIC_SLURM_PROFILE_CATALOG_REF)
PUBLIC_HELPER_NODE_INVENTORY_REF = "scripts/fixtures/public_simulation_helper_nodes.json"
PUBLIC_HELPER_NODE_INVENTORY = _find_repo_file(PUBLIC_HELPER_NODE_INVENTORY_REF)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _write_json(path: Path, data: dict) -> Path:
    path.write_text(json.dumps(data, indent=2))
    return path


def _helper_node_inventory_table() -> pd.DataFrame:
    rows = json.loads(PUBLIC_HELPER_NODE_INVENTORY.read_text())
    columns = [
        "node",
        "private_capability",
        "private_anchor",
        "why_helper_exists",
        "gdsfactory_home",
        "public_api_or_artifact",
        "public_status",
        "promotion_gate",
        "missing_evidence",
        "next_issue",
    ]
    return pd.DataFrame(rows).loc[:, columns]


def _artifact_status(output_dir: Path) -> dict[str, bool]:
    return {
        name: (output_dir / name).exists()
        for name in ("palace.msh", "config.json", "mesh_manifest.json", "palace_index_map.json")
    }


def _resolve_public_slurm_profile(
    profile_name: str,
    *,
    num_processes: int = 1,
    num_threads: int = 1,
):
    resource_overrides = {}
    if num_processes != 1:
        resource_overrides["ntasks_per_node"] = num_processes
    if num_threads != 1:
        resource_overrides["cpus_per_task"] = num_threads
    profiles = load_palace_slurm_profile_catalog(PUBLIC_SLURM_PROFILE_CATALOG)
    return resolve_palace_slurm_profile(
        profiles,
        profile_name,
        resource_overrides=resource_overrides,
    )


def _slurm_script_preview(script_path: Path) -> list[str]:
    return [
        line
        for line in script_path.read_text().splitlines()
        if line.startswith("#SBATCH") or line.startswith("srun")
    ]


def _public_solver_config_hints() -> dict:
    return _resolve_public_slurm_profile("public-slurm-dry-run").to_palace_config_hints()


def _index_map_lookup_table(
    output_dir: Path,
    *,
    sections: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    index_map = load_postprocessing_index_map(output_dir)
    rows = []
    for entry in sorted(
        index_map.entries,
        key=lambda row: (row.section, row.index, row.entry_name),
    ):
        if sections is not None and entry.section not in sections:
            continue
        physical_name = index_map.physical_name_for_index(entry.section, entry.index)
        reverse_indices = (
            index_map.indices_for_physical_name(physical_name, section=entry.section)
            if physical_name is not None
            else ()
        )
        attribute = entry.attributes[0] if entry.attributes else None
        attribute_entry_names = (
            [
                matched.entry_name
                for matched in index_map.entries_for_attribute(
                    attribute,
                    section=entry.section,
                )
            ]
            if attribute is not None
            else []
        )
        rows.append(
            {
                "section": entry.section,
                "index": entry.index,
                "physical_name": physical_name,
                "reverse_indices_for_physical_name": list(reverse_indices),
                "attribute": attribute,
                "entry_names_for_attribute": attribute_entry_names,
                "entry_name": entry.entry_name,
                "role": entry.role,
                "port": entry.metadata.get("port"),
                "terminal_name": entry.extra.get("terminal_name"),
                "current_source_name": entry.extra.get("current_source_name"),
                "current_source_element_index": entry.extra.get("current_source_element_index"),
                "current_source_element_count": entry.extra.get("current_source_element_count"),
                "direction": entry.extra.get("Direction"),
                "coordinate_system": entry.extra.get("CoordinateSystem"),
                "type": entry.extra.get("Type"),
            }
        )
    return pd.DataFrame(rows)


def _solver_problem_block(config: dict) -> str | None:
    solver = config.get("Solver", {})
    for name in ("Driven", "Eigenmode", "Electrostatic", "Magnetostatic", "Transient"):
        if name in solver:
            return name
    return None


def _domain_material_table(output_dir: Path) -> pd.DataFrame:
    frame = load_domain_material_summary(output_dir)
    columns = [
        "domain_index",
        "physical_name",
        "stack_material_name",
        "matched_material_name",
        "material_model_source",
        "material_within_validity",
        "material_frequency_ghz",
        "permittivity",
        "loss_tangent",
        "conductivity",
        "permeability",
    ]
    selected_columns = [column for column in columns if column in frame.columns]
    return frame.loc[:, selected_columns].copy()


def _config_generation_summary(
    config: dict,
    output_dir: Path,
    domain_materials: pd.DataFrame,
) -> dict:
    material_resolution = _load_json(output_dir / "palace_material_resolution.json")
    boundaries = config.get("Boundaries", {})
    postprocessing = boundaries.get("Postprocessing", {})
    surface_currents = boundaries.get("SurfaceCurrent", ())
    domains = config.get("Domains", {})
    solver = config.get("Solver", {})
    return {
        "problem_type": config["Problem"]["Type"],
        "solver_device": solver.get("Device"),
        "solver_problem_block": _solver_problem_block(config),
        "solver_has_linear": bool(solver.get("Linear")),
        "domain_material_count": len(domains.get("Materials", ())),
        "material_resolution_material_count": len(material_resolution.get("materials", ())),
        "material_resolution_interface_count": len(material_resolution.get("interfaces", ())),
        "domain_material_rows": len(domain_materials),
        "domain_postprocessing_energy_count": len(
            domains.get("Postprocessing", {}).get("Energy", ())
        ),
        "surface_flux_count": len(postprocessing.get("SurfaceFlux", ())),
        "dielectric_postprocessing_count": len(postprocessing.get("Dielectric", ())),
        "lumped_port_count": len(boundaries.get("LumpedPort", ())),
        "terminal_count": len(boundaries.get("Terminal", ())),
        "surface_current_count": len(surface_currents),
        "surface_current_element_count": sum(
            len(entry.get("Elements", ())) for entry in surface_currents if isinstance(entry, dict)
        ),
        "surface_current_directions": [
            entry.get("Direction")
            for entry in surface_currents
            if isinstance(entry, dict) and "Direction" in entry
        ],
        "surface_current_coordinate_systems": sorted(
            {
                str(entry["CoordinateSystem"])
                for entry in surface_currents
                if isinstance(entry, dict) and "CoordinateSystem" in entry
            }
            | {
                str(element["CoordinateSystem"])
                for entry in surface_currents
                if isinstance(entry, dict)
                for element in entry.get("Elements", ())
                if isinstance(element, dict) and "CoordinateSystem" in element
            }
        ),
        "pmc_count": int(bool(boundaries.get("PMC"))),
        "boundary_sections": sorted(boundaries),
    }


def _public_driven_cpw_sim(output_dir: Path):
    component = cpw_straight(length=300, signal_width=10, gap=6, ground_width=40)

    sim = DrivenSim()
    sim.set_output_dir(output_dir)
    sim.set_geometry(component)
    sim.set_stack(
        include_substrate=True,
        substrate_thickness=20,
        add_oxide_dielectric=False,
        add_passivation_dielectric=False,
    )
    sim.set_airbox(margin_x=40, margin_y=40, z_above=50, z_below=10)
    sim.add_cpw_port("o1", layer="D0_TOP_M1", s_width=10, gap_width=6, length=10)
    sim.add_cpw_port(
        "o2",
        layer="D0_TOP_M1",
        s_width=10,
        gap_width=6,
        length=10,
        excited=False,
    )
    sim.set_driven(fmin=4e9, fmax=8e9, num_points=3, excitation_port="o1")
    sim.mesh(
        preset="coarse",
        refined_mesh_size=20,
        max_mesh_size=200,
        margin_x=40,
        margin_y=40,
        planar_conductors=True,
        auto_size=False,
    )
    return sim, sim._last_mesh_result


def _driven_postprocessing(mesh_result) -> dict:
    return build_postprocessing_config_from_manifest(
        mesh_result.manifest,
        surface_flux=(
            SurfaceFluxSpec(
                role="port_surface",
                flux_type="Power",
                two_sided=None,
            ),
        ),
    )


def _public_eigenmode_resonator_sim(output_dir: Path):
    component = resonator(
        length=1200,
        meanders=2,
        coupling_length=120,
        hanger_straight_length=80,
        cpw_radius=30,
        bend_npoints=8,
    )

    sim = EigenmodeSim()
    sim.set_output_dir(output_dir)
    sim.set_geometry(component)
    sim.set_stack(
        include_substrate=True,
        substrate_thickness=20,
        add_oxide_dielectric=False,
        add_passivation_dielectric=False,
    )
    sim.set_airbox(margin_x=50, margin_y=50, z_above=50, z_below=10)
    sim.set_eigenmode(num_modes=2, target=6e9)
    sim.mesh(
        preset="coarse",
        refined_mesh_size=20,
        max_mesh_size=200,
        margin_x=50,
        margin_y=50,
        planar_conductors=True,
        auto_size=False,
    )
    return sim, sim._last_mesh_result


def _eigenmode_postprocessing(mesh_result) -> dict:
    return build_postprocessing_config_from_manifest(
        mesh_result.manifest,
        surface_flux=(
            SurfaceFluxSpec(
                role="boundary_surface",
                entry_names=("absorbing",),
                flux_type="Power",
                two_sided=None,
            ),
        ),
    )


def _eigenmode_interface_postprocessing(mesh_result) -> dict:
    interface_records = {
        "public_sa_example": {
            "interface_type": "SA",
            "thickness": 0.003,
            "material_name": "AlOx_native_generic",
            "source": "public notebook fixture only",
        }
    }
    dielectric_interfaces = build_dielectric_interface_specs_from_material_kinds(
        mesh_result.manifest,
        material_kind_by_name=get_gsim_material_kind_map(),
        material_name_aliases=get_gsim_material_kind_alias_map(),
        presets=validate_interface_preset_records(interface_records),
        preset_by_interface_type={"SA": "public_sa_example"},
    )
    return build_postprocessing_config_from_manifest(
        mesh_result.manifest,
        dielectric_interfaces=dielectric_interfaces,
    )


def _public_same_layer_capacitor_electrostatic_sim(output_dir: Path):
    component = martinis2022_differential_ribbon_capacitor(
        a_um=20,
        b_um=35,
        ell_r_um=160,
    )
    positive_port = component.ports["o_mesh_positive_electrode"]
    negative_port = component.ports["o_mesh_negative_electrode"]
    positive_center = tuple(float(value) for value in positive_port.center)
    negative_center = tuple(float(value) for value in negative_port.center)

    sim = ElectrostaticSim()
    sim.set_output_dir(output_dir)
    sim.set_geometry(component)
    sim.set_stack(
        include_substrate=True,
        substrate_thickness=20,
        add_oxide_dielectric=False,
        add_passivation_dielectric=False,
    )
    sim.set_airbox(margin_x=40, margin_y=40, z_above=50, z_below=10)
    sim.add_terminal("positive", layer="D0_TOP_M1", center=positive_center)
    sim.add_terminal("negative", layer="D0_TOP_M1", center=negative_center)
    sim.set_electrostatic(save_fields=0)
    sim.mesh(
        preset="coarse",
        refined_mesh_size=20,
        max_mesh_size=200,
        margin_x=40,
        margin_y=40,
        planar_conductors=True,
        auto_size=False,
    )
    return sim, sim._last_mesh_result


def _electrostatic_postprocessing(mesh_result) -> dict:
    return build_postprocessing_config_from_manifest(mesh_result.manifest)


def _public_magnetostatic_cpw_sim(output_dir: Path):
    component = cpw_straight(length=300, signal_width=10, gap=6, ground_width=40)

    sim = MagnetostaticSim()
    sim.set_output_dir(output_dir)
    sim.set_geometry(component)
    sim.set_stack(
        include_substrate=True,
        substrate_thickness=20,
        add_oxide_dielectric=False,
        add_passivation_dielectric=False,
    )
    sim.set_airbox(margin_x=40, margin_y=40, z_above=50, z_below=10)
    sim.add_current_source(
        "signal",
        layer="D0_TOP_M1",
        center=(0, 0),
        direction=[1.0, 0.0, 0.0],
        coordinate_system="Cartesian",
    )
    sim.add_current_source(
        "return",
        elements=(
            {
                "layer": "D0_TOP_M1",
                "center": (0, 31),
                "direction": "-X",
            },
            {
                "layer": "D0_TOP_M1",
                "center": (0, -31),
                "direction": [-1.0, 0.0, 0.0],
                "coordinate_system": "Cartesian",
            },
        ),
    )
    sim.set_magnetostatic(save_fields=0)
    sim.mesh(
        preset="coarse",
        refined_mesh_size=20,
        max_mesh_size=200,
        margin_x=40,
        margin_y=40,
        planar_conductors=True,
        auto_size=False,
    )
    return sim, sim._last_mesh_result


def _magnetostatic_postprocessing(mesh_result):
    return build_postprocessing_config_from_manifest(
        mesh_result.manifest,
        include_empty_sections=False,
    )


def _local_palace_run_settings() -> tuple[dict, str | None]:
    if os.environ.get("ORPEN_RUN_LOCAL_PALACE_SMOKE") != "1":
        return {}, "set ORPEN_RUN_LOCAL_PALACE_SMOKE=1 to run local Palace smokes"

    palace_sif = os.environ.get("PALACE_SIF")
    palace_executable = os.environ.get("PALACE_EXECUTABLE")
    if not palace_sif and not palace_executable:
        return {}, "set PALACE_SIF or PALACE_EXECUTABLE for local Palace smokes"

    executable_mode = os.environ.get("PALACE_EXECUTABLE_MODE", "wrapper")
    if executable_mode not in {"wrapper", "binary"}:
        msg = "PALACE_EXECUTABLE_MODE must be 'wrapper' or 'binary'"
        raise ValueError(msg)

    run_kwargs = {
        "use_apptainer": palace_sif is not None,
        "num_processes": int(os.environ.get("PALACE_NP", "1")),
        "num_threads": int(os.environ.get("PALACE_NT", "1")),
        "verbose": False,
    }
    if palace_sif is not None:
        run_kwargs["palace_sif_path"] = palace_sif
    else:
        run_kwargs["palace_executable"] = palace_executable
        run_kwargs["executable_mode"] = executable_mode
        run_kwargs["serial"] = os.environ.get("PALACE_SERIAL") == "1"
    return run_kwargs, None


def _run_driven_local_smoke(output_dir: Path, run_kwargs: dict) -> dict:
    sim, mesh_result = _public_driven_cpw_sim(output_dir)
    sim.write_config(
        postprocessing=_driven_postprocessing(mesh_result),
        validate_mesh=False,
        material_overlay=get_gsim_material_overlay(),
    )

    results = sim.run_local(**run_kwargs)
    report = load_driven_report(output_dir)
    return {
        "problem_type": "Driven",
        "port_names": list(report.sparams.port_names),
        "frequency_points": int(len(report.sparams.freq)),
        "port_epr_rows": int(len(report.port_epr)),
        "source_rows": int(len(report.sources)),
        "has_port_s": "port-S.csv" in results.files,
        "port_s_bytes": int(results.files["port-S.csv"].stat().st_size),
    }


def _run_eigenmode_local_smoke(output_dir: Path, run_kwargs: dict) -> dict:
    sim, mesh_result = _public_eigenmode_resonator_sim(output_dir)
    sim.write_config(
        postprocessing=_eigenmode_postprocessing(mesh_result),
        validate_mesh=False,
        material_overlay=get_gsim_material_overlay(),
    )

    results = sim.run_local(**run_kwargs)
    report = load_eigenmode_report(results)
    return {
        "problem_type": "Eigenmode",
        "mode_count": int(report.eigenmodes.n_modes),
        "min_frequency_ghz": float(report.eigenmodes.freq_real_ghz.min()),
        "domain_energy_rows": int(len(report.domain_energy)),
        "eig_bytes": int(results["eig.csv"].stat().st_size),
    }


def _run_electrostatic_local_smoke(output_dir: Path, run_kwargs: dict) -> dict:
    sim, mesh_result = _public_same_layer_capacitor_electrostatic_sim(output_dir)
    sim.write_config(
        postprocessing=_electrostatic_postprocessing(mesh_result),
        validate_mesh=False,
        material_overlay=get_gsim_material_overlay(),
    )

    results = sim.run_local(**run_kwargs)
    report = load_electrostatic_report(results)
    return {
        "problem_type": "Electrostatic",
        "terminal_names": list(report.capacitance.terminal_names),
        "matrix_shape": list(report.capacitance.dataframe.shape),
        "has_mutual_matrix": report.mutual_capacitance is not None,
        "has_inverse_matrix": report.inverse_capacitance is not None,
        "terminal_c_bytes": int(results["terminal-C.csv"].stat().st_size),
    }


def _display_report_table(
    title: str,
    frame: pd.DataFrame,
    columns: tuple[str, ...],
    max_rows: int = 8,
) -> pd.DataFrame:
    """Display a publication-safe subset of a reusable `gsim` report table."""

    selected_columns = [column for column in columns if column in frame.columns]
    preview = (
        frame.loc[:, selected_columns].head(max_rows).copy() if selected_columns else pd.DataFrame()
    )
    display(
        {
            "table": title,
            "rows": int(len(frame)),
            "shown_columns": selected_columns,
        }
    )
    display(preview)
    return preview


def _public_report_material_resolution() -> dict:
    return {
        "schema_version": 1,
        "materials": [
            {
                "material_row_index": 1,
                "material_attribute": 10,
                "material_attributes": [10],
                "volume_name": "substrate",
                "stack_material_name": "Si",
                "matched_material_name": "Si",
                "evaluation_frequency_hz": 5.0e9,
                "evaluation_frequency_ghz": 5.0,
                "model_type": "constant",
                "model_source": "orpen-sc-pdk tech.material_properties",
                "within_validity": True,
                "validity_note": None,
                "effective_material": {
                    "permittivity": 11.45,
                    "loss_tangent": 2.0e-6,
                },
                "palace_material": {
                    "Attributes": [10],
                    "Name": "Si",
                    "Permittivity": 11.45,
                    "LossTan": 2.0e-6,
                },
            }
        ],
        "interfaces": [
            {
                "interface_row_index": 1,
                "surface_index": 2,
                "surface_attributes": [20],
                "interface_type": "SA",
                "interface_material_name": "AlOx_native_generic",
                "matched_material_name": "AlOx_native_generic",
                "evaluation_frequency_hz": 5.0e9,
                "evaluation_frequency_ghz": 5.0,
                "model_type": "constant",
                "model_source": "orpen-sc-pdk tech.material_properties",
                "within_validity": True,
                "validity_note": None,
                "effective_material": {
                    "permittivity": 10.0,
                    "loss_tangent": 0.0017,
                },
                "palace_interface": {
                    "Index": 2,
                    "Attributes": [20],
                    "Type": "SA",
                    "Thickness": 0.003,
                    "Permittivity": 10.0,
                    "LossTan": 0.0017,
                },
            }
        ],
    }


def _write_public_driven_report_fixture(output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    port_info_path = _write_json(
        output_dir / "port_information.json",
        {
            "ports": [
                {"portnumber": 1, "name": "o1", "Z0": 50.0, "type": "cpw"},
                {"portnumber": 2, "name": "o2", "Z0": 50.0, "type": "cpw"},
            ],
            "unit": 1e-6,
            "name": "palace",
        },
    )
    port_s_path = output_dir / "port-S.csv"
    port_s_path.write_text(
        "f (GHz), |S[1][1]| (dB), arg(S[1][1]) (deg.), "
        "|S[2][1]| (dB), arg(S[2][1]) (deg.)\n"
        "4.0, -18.0, -45.0, -3.0, -90.0\n"
        "6.0, -12.0, -50.0, -2.0, -95.0\n"
        "8.0, -16.0, -55.0, -4.0, -100.0\n"
    )
    port_epr_path = output_dir / "port-EPR.csv"
    port_epr_path.write_text("m, p[3], p[4]\n1, 0.60, 0.40\n")
    config_path = _write_json(
        output_dir / "config.json",
        {
            "Domains": {
                "Materials": [
                    {
                        "Attributes": [10],
                        "Name": "Si",
                        "Permittivity": 11.45,
                        "LossTan": 2.0e-6,
                    }
                ]
            }
        },
    )
    index_map_path = _write_json(
        output_dir / "palace_index_map.json",
        {
            "schema_version": 1,
            "entries": [
                {
                    "section": "Domains.Postprocessing.Energy",
                    "index": 1,
                    "entry_name": "substrate",
                    "role": "dielectric_volume",
                    "attributes": [10],
                    "physical_names": ["D1_SUBSTRATE"],
                    "dimension": 3,
                },
                {
                    "section": "Boundaries.Postprocessing.SurfaceFlux",
                    "index": 3,
                    "entry_name": "o1_port_surface",
                    "role": "port_surface",
                    "attributes": [31],
                    "physical_names": ["P1_E0"],
                    "dimension": 2,
                    "Type": "Power",
                    "metadata": {"port": "P1", "port_type": "cpw"},
                },
                {
                    "section": "Boundaries.Postprocessing.SurfaceFlux",
                    "index": 4,
                    "entry_name": "o2_port_surface",
                    "role": "port_surface",
                    "attributes": [41],
                    "physical_names": ["P2_E0"],
                    "dimension": 2,
                    "Type": "Power",
                    "metadata": {"port": "P2", "port_type": "cpw"},
                },
            ],
        },
    )
    material_resolution_path = _write_json(
        output_dir / "palace_material_resolution.json",
        _public_report_material_resolution(),
    )
    return {
        "port-S.csv": port_s_path,
        "port-EPR.csv": port_epr_path,
        "port_information.json": port_info_path,
        "config.json": config_path,
        "palace_index_map.json": index_map_path,
        "palace_material_resolution.json": material_resolution_path,
    }


def _write_public_eigenmode_report_fixture(output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    eig_path = output_dir / "eig.csv"
    eig_path.write_text(
        "m, Re{f} (GHz), Im{f} (GHz), Q, Error (Bkwd.), Error (Abs.)\n"
        "1, 5.0, 0.0, 2.0e6, 0.0, 0.0\n"
    )
    domain_e_path = output_dir / "domain-E.csv"
    domain_e_path.write_text("m, E_elec[1] (J), p_elec[1]\n1, 1.0, 0.25\n")
    surface_q_path = output_dir / "surface-Q.csv"
    surface_q_path.write_text("m, p_surf[2], Q_surf[2]\n1, 0.125, 1.0e6\n")
    config_path = _write_json(
        output_dir / "config.json",
        {
            "Domains": {
                "Materials": [
                    {
                        "Attributes": [10],
                        "Name": "Si",
                        "Permittivity": 11.45,
                        "LossTan": 2.0e-6,
                    }
                ]
            },
            "Boundaries": {
                "Postprocessing": {
                    "Dielectric": [
                        {
                            "Index": 2,
                            "Attributes": [20],
                            "Type": "SA",
                            "Thickness": 0.003,
                            "Permittivity": 10.0,
                            "LossTan": 0.0017,
                        }
                    ]
                }
            },
        },
    )
    index_map_path = _write_json(
        output_dir / "palace_index_map.json",
        {
            "schema_version": 1,
            "entries": [
                {
                    "section": "Domains.Postprocessing.Energy",
                    "index": 1,
                    "entry_name": "substrate",
                    "role": "dielectric_volume",
                    "attributes": [10],
                    "physical_names": ["D1_SUBSTRATE"],
                    "dimension": 3,
                },
                {
                    "section": "Boundaries.Postprocessing.Dielectric",
                    "index": 2,
                    "entry_name": "sa_interface",
                    "role": "boundary_surface",
                    "attributes": [20],
                    "physical_names": ["SA:D1_SUBSTRATE___OUTER_VACUUM"],
                    "dimension": 2,
                    "Type": "SA",
                },
            ],
        },
    )
    material_resolution_path = _write_json(
        output_dir / "palace_material_resolution.json",
        _public_report_material_resolution(),
    )
    return {
        "eig.csv": eig_path,
        "domain-E.csv": domain_e_path,
        "surface-Q.csv": surface_q_path,
        "config.json": config_path,
        "palace_index_map.json": index_map_path,
        "palace_material_resolution.json": material_resolution_path,
    }


def _write_public_electrostatic_report_fixture(output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    terminal_c_path = output_dir / "terminal-C.csv"
    terminal_c_path.write_text(
        "i, C[i][1] (F), C[i][2] (F)\n1.00e+00, 1.0e-15, -2.0e-15\n2.00e+00, -2.0e-15, 4.0e-15\n"
    )
    domain_e_path = output_dir / "domain-E.csv"
    domain_e_path.write_text("i, E_elec[1] (J), p_elec[1]\n1, 1.0, 0.25\n2, 1.0, 0.125\n")
    surface_q_path = output_dir / "surface-Q.csv"
    surface_q_path.write_text("i, p_surf[2], Q_surf[2]\n1, 0.125, 1.0e6\n2, 0.25, 2.0e6\n")
    config_path = _write_json(
        output_dir / "config.json",
        {
            "Domains": {
                "Materials": [
                    {
                        "Attributes": [10],
                        "Name": "Si",
                        "Permittivity": 11.45,
                        "LossTan": 2.0e-6,
                    }
                ]
            },
            "Boundaries": {
                "Postprocessing": {
                    "Dielectric": [
                        {
                            "Index": 2,
                            "Attributes": [20],
                            "Type": "SA",
                            "Thickness": 0.003,
                            "Permittivity": 10.0,
                            "LossTan": 0.0017,
                        }
                    ]
                }
            },
        },
    )
    index_map_path = _write_json(
        output_dir / "palace_index_map.json",
        {
            "schema_version": 1,
            "entries": [
                {
                    "section": "Boundaries.Terminal",
                    "index": 1,
                    "entry_name": "positive_electrode",
                    "role": "pec_surface",
                    "attributes": [11],
                    "physical_names": ["D0_TOP_M1@positive"],
                    "dimension": 2,
                    "terminal_name": "positive",
                },
                {
                    "section": "Boundaries.Terminal",
                    "index": 2,
                    "entry_name": "negative_electrode",
                    "role": "pec_surface",
                    "attributes": [12],
                    "physical_names": ["D0_TOP_M1@negative"],
                    "dimension": 2,
                    "terminal_name": "negative",
                },
                {
                    "section": "Domains.Postprocessing.Energy",
                    "index": 1,
                    "entry_name": "substrate",
                    "role": "dielectric_volume",
                    "attributes": [10],
                    "physical_names": ["D1_SUBSTRATE"],
                    "dimension": 3,
                },
                {
                    "section": "Boundaries.Postprocessing.Dielectric",
                    "index": 2,
                    "entry_name": "sa_interface",
                    "role": "boundary_surface",
                    "attributes": [20],
                    "physical_names": ["SA:D1_SUBSTRATE___OUTER_VACUUM"],
                    "dimension": 2,
                    "Type": "SA",
                },
            ],
        },
    )
    material_resolution_path = _write_json(
        output_dir / "palace_material_resolution.json",
        _public_report_material_resolution(),
    )
    return {
        "terminal-C.csv": terminal_c_path,
        "domain-E.csv": domain_e_path,
        "surface-Q.csv": surface_q_path,
        "config.json": config_path,
        "palace_index_map.json": index_map_path,
        "palace_material_resolution.json": material_resolution_path,
    }


# %% [markdown]
# ## Helper-node coverage matrix
#
# This table is the public migration inventory for the simulation helper
# system. It records the private capability shape, why a helper node exists,
# the intended GDSFactory ecosystem home, the current public API/artifact, and
# the issue that owns the next slice. Magnetostatic is covered here as a public
# config fixture while solver report parsing remains a later slice.

# %%
helper_node_inventory = _helper_node_inventory_table()
with pd.option_context("display.max_columns", None, "display.max_colwidth", None):
    display(helper_node_inventory)

# %% [markdown]
# ## Slurm profile catalog and handoff controls
#
# Public fixtures keep real site profile catalogs outside the PDK. The notebook
# still exercises the reusable `gsim` profile helpers by loading a public dry-run
# catalog, resolving resource overrides, and exposing the launcher/solver hints
# that feed generated Palace Slurm scripts.

# %%
profile_catalog = load_palace_slurm_profile_catalog(PUBLIC_SLURM_PROFILE_CATALOG)
resolved_profile = _resolve_public_slurm_profile(
    "public-slurm-dry-run",
    num_processes=2,
    num_threads=1,
)
profile_catalog_summary = {
    "catalog_path": PUBLIC_SLURM_PROFILE_CATALOG_REF,
    "profile_names": sorted(profile_catalog),
    "resolved_profile": resolved_profile.name,
    "resolved_resources": resolved_profile.resources.to_dict(),
    "launcher_kwargs": resolved_profile.launcher.to_sbatch_kwargs(),
    "solver_hints": dict(resolved_profile.solver),
    "config_hints": resolved_profile.to_palace_config_hints(),
    "profile_metadata": dict(resolved_profile.profile),
}

display(profile_catalog_summary)

# %% [markdown]
# ## Slurm handoff script preview
#
# The next cell writes a docs-safe dry-run handoff beside placeholder public
# Palace artifacts. This previews the exact helper-function path used by the
# evidence runner: profile catalog loading, profile resolution, `sbatch` spec
# construction, sidecar writing, and summary reload.

# %%
with tempfile.TemporaryDirectory() as temp_dir:
    output_dir = Path(temp_dir) / "slurm-handoff-preview"
    output_dir.mkdir(parents=True)
    _write_json(output_dir / "config.json", {"Problem": {"Type": "Eigenmode"}})
    (output_dir / "palace.msh").write_text("$MeshFormat\n2.2 0 8\n$EndMeshFormat\n")

    handoff_profile = _resolve_public_slurm_profile(
        "public-slurm-dry-run",
        num_processes=2,
        num_threads=1,
    )
    handoff_result = write_palace_slurm_sbatch_handoff(
        output_dir,
        PalaceSlurmSbatchSpec(
            job_name="palace_public_notebook",
            resources=handoff_profile.resources,
            **handoff_profile.launcher.to_sbatch_kwargs(),
        ),
        profile=handoff_profile.profile,
        metadata={"workflow": "public-simulation-workflows"},
    )
    handoff_summary = load_palace_run_summary(output_dir)
    handoff_preview = {
        "script_name": handoff_result.script_path.name,
        "metadata_name": handoff_result.metadata_path.name,
        "handoff_status": handoff_summary.handoff["status"],
        "profile": handoff_summary.handoff["profile"],
        "resolved_resources": handoff_summary.handoff["resources"]["resolved"],
        "script_lines": _slurm_script_preview(handoff_result.script_path),
    }

display(handoff_preview)

# %% [markdown]
# ## Driven CPW workflow
#
# The driven fixture uses a public CPW straight with two CPW ports. The workflow
# writes a Driven `config.json`, mesh manifest, and Palace index map that links
# CPW port-surface `SurfaceFlux` indices back to generated port metadata.

# %%
with tempfile.TemporaryDirectory() as temp_dir:
    output_dir = Path(temp_dir) / "driven-cpw"
    sim, mesh_result = _public_driven_cpw_sim(output_dir)
    config_hints = _public_solver_config_hints()
    config_path = sim.write_config(
        postprocessing=_driven_postprocessing(mesh_result),
        validate_mesh=False,
        material_overlay=get_gsim_material_overlay(),
        hints=config_hints,
    )
    config = _load_json(config_path)
    index_map = _load_json(output_dir / "palace_index_map.json")
    driven_domain_materials = _domain_material_table(output_dir)
    driven_index_lookup = _index_map_lookup_table(output_dir)
    driven_summary = {
        "problem_type": config["Problem"]["Type"],
        "profile_config_hints": config_hints,
        "solver_device": config["Solver"].get("Device"),
        "config_generation": _config_generation_summary(
            config,
            output_dir,
            driven_domain_materials,
        ),
        "artifacts": _artifact_status(output_dir),
        "lumped_port_count": len(config["Boundaries"]["LumpedPort"]),
        "surface_flux_rows": len(config["Boundaries"]["Postprocessing"]["SurfaceFlux"]),
        "index_lookup_rows": len(driven_index_lookup),
        "indexed_ports": sorted(
            {
                row["metadata"]["port"]
                for row in index_map["entries"]
                if row["section"] == "Boundaries.Postprocessing.SurfaceFlux"
            }
        ),
    }

display(driven_summary)
display(driven_domain_materials)
display(driven_index_lookup)

# %% [markdown]
# ## Eigenmode resonator workflow
#
# The eigenmode fixture uses a public resonator cell. The workflow writes an
# Eigenmode `config.json`, mesh manifest, and Palace index map that links the
# absorbing boundary `SurfaceFlux` index back to the generated physical name.

# %%
with tempfile.TemporaryDirectory() as temp_dir:
    output_dir = Path(temp_dir) / "eigenmode-resonator"
    sim, mesh_result = _public_eigenmode_resonator_sim(output_dir)
    config_hints = _public_solver_config_hints()
    config_path = sim.write_config(
        postprocessing=_eigenmode_postprocessing(mesh_result),
        validate_mesh=False,
        material_overlay=get_gsim_material_overlay(),
        hints=config_hints,
    )
    config = _load_json(config_path)
    index_map = _load_json(output_dir / "palace_index_map.json")
    eigenmode_domain_materials = _domain_material_table(output_dir)
    eigenmode_index_lookup = _index_map_lookup_table(output_dir)
    eigenmode_summary = {
        "problem_type": config["Problem"]["Type"],
        "profile_config_hints": config_hints,
        "solver_device": config["Solver"].get("Device"),
        "config_generation": _config_generation_summary(
            config,
            output_dir,
            eigenmode_domain_materials,
        ),
        "artifacts": _artifact_status(output_dir),
        "energy_rows": len(config["Domains"]["Postprocessing"]["Energy"]),
        "index_lookup_rows": len(eigenmode_index_lookup),
        "surface_flux_names": sorted(
            {
                row["entry_name"]
                for row in index_map["entries"]
                if row["section"] == "Boundaries.Postprocessing.SurfaceFlux"
            }
        ),
    }

display(eigenmode_summary)
display(eigenmode_domain_materials)
display(eigenmode_index_lookup)

# %% [markdown]
# ## Caller-supplied Eigenmode interface classification
#
# Generated mesh manifests can expose material interfaces such as
# `air___silicon`. Public workflows keep MA/MS/SA preset values caller-supplied
# until source-backed defaults are accepted into the PDK contract. This example
# classifies the generated resonator substrate-air interface through OrPen's
# public material-kind and alias helpers, then lets `gsim` write and reload the
# Palace dielectric-interface provenance.

# %%
with tempfile.TemporaryDirectory() as temp_dir:
    output_dir = Path(temp_dir) / "eigenmode-interface"
    sim, mesh_result = _public_eigenmode_resonator_sim(output_dir)
    config_hints = _public_solver_config_hints()
    config_path = sim.write_config(
        postprocessing=_eigenmode_interface_postprocessing(mesh_result),
        validate_mesh=False,
        material_overlay=get_gsim_material_overlay(),
        hints=config_hints,
    )
    config = _load_json(config_path)
    interface_domain_materials = _domain_material_table(output_dir)
    interface_summary = load_dielectric_interface_summary(
        {
            "config.json": config_path,
            "palace_index_map.json": output_dir / "palace_index_map.json",
        }
    )
    interface_index_lookup = _index_map_lookup_table(
        output_dir,
        sections=("Boundaries.Postprocessing.Dielectric",),
    )
    interface_preview = interface_summary.loc[
        :,
        [
            "surface_index",
            "source_name",
            "interface_type",
            "preset_name",
            "preset_source",
            "interface_material_name",
            "matched_material_name",
            "material_model_source",
            "permittivity",
            "loss_tangent",
        ],
    ]
    generated_interface_summary = {
        "problem_type": config["Problem"]["Type"],
        "profile_config_hints": config_hints,
        "solver_device": config["Solver"].get("Device"),
        "config_generation": _config_generation_summary(
            config,
            output_dir,
            interface_domain_materials,
        ),
        "dielectric_interface_rows": len(config["Boundaries"]["Postprocessing"]["Dielectric"]),
        "index_lookup_rows": len(interface_index_lookup),
        "classified_interfaces": interface_preview.to_dict(orient="records"),
    }

display(generated_interface_summary)
display(interface_domain_materials)
display(interface_index_lookup)

# %% [markdown]
# ## Electrostatic same-layer capacitor workflow
#
# The electrostatic fixture uses the public Martinis differential ribbon
# capacitor. Both electrodes live on the same metal layer, so the workflow uses
# `gsim` center-selected terminals to map positive and negative terminals to
# separate same-layer PEC islands.

# %%
with tempfile.TemporaryDirectory() as temp_dir:
    output_dir = Path(temp_dir) / "electrostatic-capacitor"
    sim, mesh_result = _public_same_layer_capacitor_electrostatic_sim(output_dir)
    config_hints = _public_solver_config_hints()
    config_path = sim.write_config(
        postprocessing=_electrostatic_postprocessing(mesh_result),
        validate_mesh=False,
        material_overlay=get_gsim_material_overlay(),
        hints=config_hints,
    )
    config = _load_json(config_path)
    index_map = _load_json(output_dir / "palace_index_map.json")
    electrostatic_domain_materials = _domain_material_table(output_dir)
    electrostatic_index_lookup = _index_map_lookup_table(output_dir)
    electrostatic_summary = {
        "problem_type": config["Problem"]["Type"],
        "profile_config_hints": config_hints,
        "solver_device": config["Solver"].get("Device"),
        "config_generation": _config_generation_summary(
            config,
            output_dir,
            electrostatic_domain_materials,
        ),
        "artifacts": _artifact_status(output_dir),
        "terminal_count": len(config["Boundaries"]["Terminal"]),
        "index_lookup_rows": len(electrostatic_index_lookup),
        "terminal_names": sorted(
            {
                row["terminal_name"]
                for row in index_map["entries"]
                if row["section"] == "Boundaries.Terminal"
            }
        ),
        "terminal_layer_names": sorted(
            {
                row["metadata"]["layer"]
                for row in index_map["entries"]
                if row["section"] == "Boundaries.Terminal"
            }
        ),
    }

display(electrostatic_summary)
display(electrostatic_domain_materials)
display(electrostatic_index_lookup)

# %% [markdown]
# ## Magnetostatic CPW source workflow
#
# The magnetostatic fixture uses the public CPW straight cell. The workflow uses
# `gsim` center-selected current sources to map signal and multielement return
# current sources to separate same-layer PEC islands, then writes
# `SurfaceCurrent`, `PMC`, and magnetic `SurfaceFlux` entries without
# hand-editing Palace JSON.

# %%
with tempfile.TemporaryDirectory() as temp_dir:
    output_dir = Path(temp_dir) / "magnetostatic-cpw"
    sim, mesh_result = _public_magnetostatic_cpw_sim(output_dir)
    config_hints = _public_solver_config_hints()
    config_path = sim.write_config(
        postprocessing=_magnetostatic_postprocessing(mesh_result),
        validate_mesh=False,
        material_overlay=get_gsim_material_overlay(),
        hints=config_hints,
    )
    config = _load_json(config_path)
    index_map = _load_json(output_dir / "palace_index_map.json")
    magnetostatic_domain_materials = _domain_material_table(output_dir)
    magnetostatic_index_lookup = _index_map_lookup_table(output_dir)
    magnetostatic_summary = {
        "problem_type": config["Problem"]["Type"],
        "profile_config_hints": config_hints,
        "solver_device": config["Solver"].get("Device"),
        "config_generation": _config_generation_summary(
            config,
            output_dir,
            magnetostatic_domain_materials,
        ),
        "artifacts": _artifact_status(output_dir),
        "surface_current_count": len(config["Boundaries"]["SurfaceCurrent"]),
        "surface_flux_rows": len(config["Boundaries"]["Postprocessing"]["SurfaceFlux"]),
        "pmc_attributes": config["Boundaries"].get("PMC", {}).get("Attributes", []),
        "surface_current_element_count": sum(
            len(entry.get("Elements", ())) for entry in config["Boundaries"]["SurfaceCurrent"]
        ),
        "surface_current_coordinate_systems": sorted(
            set(magnetostatic_index_lookup["coordinate_system"].dropna().astype(str).tolist())
        ),
        "index_lookup_rows": len(magnetostatic_index_lookup),
        "current_source_names": sorted(
            {
                row["current_source_name"]
                for row in index_map["entries"]
                if row["section"] == "Boundaries.SurfaceCurrent"
            }
        ),
        "surface_flux_types": sorted(
            {
                row["Type"]
                for row in index_map["entries"]
                if row["section"] == "Boundaries.Postprocessing.SurfaceFlux"
            }
        ),
    }

display(magnetostatic_summary)
display(magnetostatic_domain_materials)
display(magnetostatic_index_lookup)

# %% [markdown]
# ## Reusable report table displays
#
# The report examples use synthetic public Palace artifacts so the docs build
# can exercise the same `gsim` report loaders without requiring a local Palace
# executable or publishing private solver output. The display helper keeps the
# notebook presentation layer separate from `gsim` report parsing.

# %%
with tempfile.TemporaryDirectory() as temp_dir:
    source = _write_public_driven_report_fixture(Path(temp_dir) / "driven-report")
    driven_report = load_driven_report(source)

    driven_sparams = _display_report_table(
        "Driven S-parameters",
        driven_report.sparams.to_dataframe(),
        (
            "freq_ghz",
            "S_o1_o1_db",
            "S_o2_o1_db",
            "S_o1_o1_deg",
            "S_o2_o1_deg",
        ),
    )
    driven_port_epr = _display_report_table(
        "Driven port EPR",
        driven_report.port_epr,
        (
            "mode_index",
            "port_index",
            "source_name",
            "entry_name",
            "postprocessing_type",
            "p_port",
            "abs_p_port_fraction",
        ),
    )

display(
    {
        "driven_frequency_rows": len(driven_sparams),
        "driven_port_epr_rows": len(driven_port_epr),
        "driven_missing_reports": list(driven_report.missing_reports),
    }
)

# %%
with tempfile.TemporaryDirectory() as temp_dir:
    source = _write_public_eigenmode_report_fixture(Path(temp_dir) / "eigenmode-report")
    eigenmode_report = load_eigenmode_report(source)

    eigenmode_loss_budget = _display_report_table(
        "Eigenmode loss budget",
        eigenmode_report.loss_budget,
        (
            "mode_index",
            "frequency_ghz",
            "domain_inverse_q_sum",
            "surface_inverse_q_sum",
            "total_inverse_q_sum",
            "q_total",
            "t1_us",
        ),
    )
    eigenmode_domain_loss = _display_report_table(
        "Eigenmode domain loss",
        eigenmode_report.domain_loss,
        (
            "mode_index",
            "domain_index",
            "source_name",
            "material_name",
            "matched_material_name",
            "material_model_source",
            "p_elec",
            "loss_tangent",
            "inverse_q",
        ),
    )
    eigenmode_surface_loss = _display_report_table(
        "Eigenmode surface loss",
        eigenmode_report.surface_loss,
        (
            "mode_index",
            "surface_index",
            "source_name",
            "interface_type",
            "preset_name",
            "preset_source",
            "interface_material_name",
            "matched_material_name",
            "material_model_source",
            "p_surf",
            "loss_tangent",
            "inverse_q",
        ),
    )

display(
    {
        "eigenmode_loss_budget_rows": len(eigenmode_loss_budget),
        "eigenmode_domain_loss_rows": len(eigenmode_domain_loss),
        "eigenmode_surface_loss_rows": len(eigenmode_surface_loss),
    }
)

# %%
with tempfile.TemporaryDirectory() as temp_dir:
    source = _write_public_electrostatic_report_fixture(Path(temp_dir) / "electrostatic-report")
    electrostatic_report = load_electrostatic_report(source, frequency_ghz=5.0)

    electrostatic_loss_budget = _display_report_table(
        "Electrostatic loss budget",
        electrostatic_report.loss_budget,
        (
            "source_index",
            "domain_inverse_q_sum",
            "surface_inverse_q_sum",
            "total_inverse_q_sum",
            "q_total",
            "gamma_hz",
            "t1_us",
        ),
    )
    electrostatic_domain_loss = _display_report_table(
        "Electrostatic domain loss",
        electrostatic_report.domain_loss,
        (
            "source_index",
            "domain_index",
            "source_name",
            "material_name",
            "matched_material_name",
            "material_model_source",
            "p_elec",
            "loss_tangent",
            "inverse_q",
            "t1_us",
        ),
    )
    electrostatic_surface_loss = _display_report_table(
        "Electrostatic surface loss",
        electrostatic_report.surface_loss,
        (
            "source_index",
            "surface_index",
            "source_name",
            "interface_type",
            "preset_name",
            "preset_source",
            "interface_material_name",
            "matched_material_name",
            "material_model_source",
            "p_surf",
            "loss_tangent",
            "inverse_q",
            "t1_us",
        ),
    )

display(
    {
        "electrostatic_loss_budget_rows": len(electrostatic_loss_budget),
        "electrostatic_domain_loss_rows": len(electrostatic_domain_loss),
        "electrostatic_surface_loss_rows": len(electrostatic_surface_loss),
    }
)

# %% [markdown]
# ## Optional local Palace smoke solves
#
# The next cell is intentionally opt-in. Normal docs builds display a skip
# reason instead of invoking a solver. To run the public coarse solves locally,
# set `ORPEN_RUN_LOCAL_PALACE_SMOKE=1` and either `PALACE_SIF` or
# `PALACE_EXECUTABLE`. For direct development binaries that do not accept
# wrapper launcher flags, also set `PALACE_EXECUTABLE_MODE=binary`.

# %%
with tempfile.TemporaryDirectory() as temp_dir:
    output_root = Path(temp_dir) / "local-palace-smokes"
    run_kwargs, skip_reason = _local_palace_run_settings()
    local_smoke_summary = {
        "enabled": skip_reason is None,
        "skip_reason": skip_reason,
        "problems": [],
    }

    if skip_reason is None:
        local_smoke_summary["problems"] = [
            _run_driven_local_smoke(output_root / "driven-cpw", run_kwargs),
            _run_eigenmode_local_smoke(output_root / "eigenmode-resonator", run_kwargs),
            _run_electrostatic_local_smoke(output_root / "electrostatic-capacitor", run_kwargs),
        ]

display(local_smoke_summary)

# %% [markdown]
# ## Local solve boundary
#
# These examples prove public geometry, material/layer metadata, automatic
# Palace config generation, mesh physical-name manifests, index-map artifacts,
# reusable report display tables, and opt-in local solver smoke execution. A
# full Palace solve is intentionally outside the default docs build. The
# report-backed local smoke cell covers Driven, Eigenmode, and Electrostatic;
# Magnetostatic is currently covered through config/index-map generation until
# a public report parser is added.
