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

    .. grid-item-card:: NB-001 Public PDK Quickstart

        :doc:`notebooks/public_pdk_quickstart`

        Activates the open PDK, builds public demo components, and inspects the
        public PDK registry.

    .. grid-item-card:: NB-002 Public Driven Workflow

        :doc:`notebooks/public_driven_workflow`

        Builds the public CPW Driven fixture, generated Palace mesh/config
        artifacts, material/index provenance tables, synthetic report displays,
        and an opt-in local solver smoke.

    .. grid-item-card:: NB-003 Public Eigenmode Workflow

        :doc:`notebooks/public_eigenmode_workflow`

        Builds the public resonator Eigenmode fixture, generated Palace
        mesh/config artifacts, caller-supplied interface classification,
        synthetic report displays, and an opt-in local solver smoke.

    .. grid-item-card:: NB-004 Public Electrostatic Workflow

        :doc:`notebooks/public_electrostatic_workflow`

        Builds the public same-layer capacitor Electrostatic fixture, generated
        Palace mesh/config artifacts, terminal provenance, synthetic report
        displays, and an opt-in local solver smoke.

    .. grid-item-card:: NB-005 Public Simulation Inventory

        :doc:`notebooks/public_simulation_inventory`

        Displays the public/private simulation notebook cross-check,
        helper-node inventory, goal-level audit status, ecosystem home, and
        issue ownership without embedding private workflow code.

    .. grid-item-card:: NB-006 Reference Qubit Workflow

        Status: private source pending.

        The public version should document the workflow shape while keeping the
        private qubit layout in the private layout repo.

    .. grid-item-card:: NB-007 Circular Qubit V3 Workflow

        Status: private source pending.

        The public version should become available only after a publication-safe
        public surface exists.

.. toctree::
    :maxdepth: 1
    :hidden:

    notebooks/public_pdk_quickstart
    notebooks/public_driven_workflow
    notebooks/public_eigenmode_workflow
    notebooks/public_electrostatic_workflow
    notebooks/public_simulation_inventory
