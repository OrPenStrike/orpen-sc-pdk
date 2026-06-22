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
        ``gsim`` Route B finite-metal shell interface groups, selects the MS
        bottom total/band/core entries for Surface EPR postprocessing, and
        records a paper-scale capacitance comparison target.

    .. grid-item-card:: NB-006 Public Eigenmode Local Workflow

        :doc:`notebooks/public_eigenmode_local_workflow`

        Builds the public resonator Eigenmode fixture and exposes a direct
        ``sim.run_local()`` Run Stage. The docs build renders this notebook but
        does not execute result cells by default.

    .. grid-item-card:: NB-007 Public Electrostatic Local Workflow

        :doc:`notebooks/public_electrostatic_local_workflow`

        Builds the public same-layer capacitor Electrostatic fixture and exposes
        a direct ``sim.run_local()`` Run Stage for local Palace execution.

    .. grid-item-card:: NB-008 Public Surface EPR Ribbon Capacitor Local Workflow

        :doc:`notebooks/public_surface_epr_ribbon_capacitor_local_workflow`

        Builds the public Martinis 2022 differential ribbon capacitor, uses
        ``gsim`` Route B finite-metal shell interface groups, selects the MS
        bottom total/band/core entries for Surface EPR postprocessing, and
        exposes a direct ``sim.run_local()`` Electrostatic Run Stage.

.. toctree::
    :maxdepth: 1
    :hidden:

    notebooks/public_driven_workflow
    notebooks/public_eigenmode_workflow
    notebooks/public_electrostatic_workflow
    notebooks/public_surface_epr_ribbon_capacitor_workflow
    notebooks/public_driven_local_workflow
    notebooks/public_eigenmode_local_workflow
    notebooks/public_electrostatic_local_workflow
    notebooks/public_surface_epr_ribbon_capacitor_local_workflow
