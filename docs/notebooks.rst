#########
Notebooks
#########

.. meta::
    :description: Public notebooks for the orpen-sc-pdk open superconducting quantum/RF PDK.

These notebooks are publication-safe examples built from the public PDK. They
avoid private chip layouts, GDS inputs from private designs, run artifacts from
private workflows, and lab-specific layout packages.

Private chip-specific resonator, reference qubit, and circular qubit V3
simulation notebooks belong in the private layout repository until their public
workflow surface can be demonstrated without publishing layout/IP. This
repository documents the static private-mount boundary and keeps notebook
examples safe for GitHub Pages.

**************
Notebook Items
**************

.. grid:: 1 1 2 3
    :gutter: 3

    .. grid-item-card:: NB-001 Public Driven Workflow

        :doc:`notebooks/public_driven_workflow`

        Builds the public CPW Driven fixture, writes the Palace run folder,
        generates ``run_palace.sbatch``, and packages the run folder with
        ``sim.generate_handoff_package()`` for manual Slurm submission.

    .. grid-item-card:: NB-002 Public Eigenmode Workflow

        :doc:`notebooks/public_eigenmode_workflow`

        Builds the public resonator Eigenmode fixture, generated Palace
        mesh/config artifacts, ``run_palace.sbatch``, and a handoff archive
        for manual Slurm submission.

    .. grid-item-card:: NB-003 Public Electrostatic Workflow

        :doc:`notebooks/public_electrostatic_workflow`

        Builds the public same-layer capacitor Electrostatic fixture, generated
        Palace mesh/config artifacts, ``run_palace.sbatch``, and a handoff
        archive for manual Slurm submission.

    .. grid-item-card:: NB-004 Public Driven Local Workflow

        :doc:`notebooks/public_driven_local_workflow`

        Builds the public CPW Driven fixture and exposes a direct
        ``sim.run_local()`` Run Stage. Set ``PALACE_RUN_LOCAL = True`` after
        configuring local Palace runtime commands.

    .. grid-item-card:: NB-005 Public Surface EPR Ribbon Capacitor Workflow

        :doc:`notebooks/public_surface_epr_ribbon_capacitor_workflow`

        Builds the public Martinis 2022 differential ribbon capacitor, uses
        ``gsim`` representation B Surface EPR, selects the MS bottom entries
        through ``sim.set_surface_epr(...)``, and
        records a paper-scale capacitance comparison target.

    .. grid-item-card:: NB-006 Public Surface EPR Ribbon Capacitor Representation A Workflow

        :doc:`notebooks/public_surface_epr_ribbon_capacitor_representation_a_workflow`

        Builds the same public Martinis 2022 differential ribbon capacitor and
        presents representation A as an independent Surface EPR workflow.

    .. grid-item-card:: NB-007 Public Eigenmode Local Workflow

        :doc:`notebooks/public_eigenmode_local_workflow`

        Builds the public resonator Eigenmode fixture and exposes a direct
        ``sim.run_local()`` Run Stage. The docs build renders this notebook but
        does not execute result cells by default.

    .. grid-item-card:: NB-008 Public Electrostatic Local Workflow

        :doc:`notebooks/public_electrostatic_local_workflow`

        Builds the public same-layer capacitor Electrostatic fixture and exposes
        a direct ``sim.run_local()`` Run Stage for local Palace execution.

    .. grid-item-card:: NB-009 Public Surface EPR Ribbon Capacitor Representation B Local Workflow

        :doc:`notebooks/public_surface_epr_ribbon_capacitor_representation_b_local_workflow`

        Builds the public Martinis 2022 differential ribbon capacitor, uses
        ``gsim`` representation B Surface EPR, selects the MS bottom entries
        through ``sim.set_surface_epr(...)``, and
        exposes a direct ``sim.run_local()`` Electrostatic Run Stage.

    .. grid-item-card:: NB-010 Public Surface EPR Ribbon Capacitor Representation C Workflow

        :doc:`notebooks/public_surface_epr_ribbon_capacitor_representation_c_workflow`

        Builds the same public Martinis 2022 differential ribbon capacitor and
        presents representation C as an independent Surface EPR workflow with
        retained-volume MA/MS/SA total physical-group and BBox validation.

    .. grid-item-card:: NB-011 Inset Surface EPR Demo

        :doc:`notebooks/Inset_Surface_EPR_Demo/martinis2022_ribbon_route_a_local`

        Groups six Martinis 2022 ribbon notebooks under
        ``Inset_Surface_EPR_Demo``: A/B/C local runs and A/B/C F1 handoff
        packages. The demo keeps material parameters, inset margins, solver
        order, and refinement controls aligned across routes.

.. toctree::
    :maxdepth: 1
    :hidden:

    notebooks/public_driven_workflow
    notebooks/public_eigenmode_workflow
    notebooks/public_electrostatic_workflow
    notebooks/public_surface_epr_ribbon_capacitor_workflow
    notebooks/public_surface_epr_ribbon_capacitor_representation_a_workflow
    notebooks/public_driven_local_workflow
    notebooks/public_eigenmode_local_workflow
    notebooks/public_electrostatic_local_workflow
    notebooks/public_surface_epr_ribbon_capacitor_representation_b_local_workflow
    notebooks/public_surface_epr_ribbon_capacitor_representation_c_workflow
    notebooks/Inset_Surface_EPR_Demo/martinis2022_ribbon_route_a_local
    notebooks/Inset_Surface_EPR_Demo/martinis2022_ribbon_route_a_hpc_handoff
    notebooks/Inset_Surface_EPR_Demo/martinis2022_ribbon_route_b_local
    notebooks/Inset_Surface_EPR_Demo/martinis2022_ribbon_route_b_hpc_handoff
    notebooks/Inset_Surface_EPR_Demo/martinis2022_ribbon_route_c_local
    notebooks/Inset_Surface_EPR_Demo/martinis2022_ribbon_route_c_hpc_handoff
