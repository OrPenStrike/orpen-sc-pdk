#########
Notebooks
#########

.. meta::
    :description: Public notebooks for the orpen-sc-pdk open superconducting quantum/RF PDK.

These notebooks are publication-safe examples built from the public PDK. The
current product surface has two tracks: SGB geometry semantics and ``gsim``
Resolve/Results.

Private chip-specific notebooks belong in the private layout repository until
their public workflow surface can be demonstrated without publishing layout/IP.

*****************
Current Notebooks
*****************

.. grid:: 1 1 2 2
    :gutter: 3

    .. grid-item-card:: SGB Geometry Tutorials

        Twelve notebooks cover four public geometries across Route A/B/C. Each
        notebook checks one geometry-route semantic contract before optional
        solver handoff. Sources live under
        ``notebooks/SGB_Geometry_Tutorials/``.

    .. grid-item-card:: Public Electrostatic Workflow

        :doc:`notebooks/public_electrostatic_workflow`

        Builds the public same-layer capacitor, writes Palace mesh/config
        artifacts, and prepares the analysis package consumed by
        Resolve/Results.

    .. grid-item-card:: Public Electrostatic Local Workflow

        :doc:`notebooks/public_electrostatic_local_workflow`

        Uses the same electrostatic fixture with direct ``sim.run_local()``
        controls for local Palace execution.

    .. grid-item-card:: Native Masked Surface EPR Handoff

        Packages an Electrostatic handoff for Palace forks that support native
        ``Dielectric.Mask`` outputs, then lets Resolve/Results own C-matrix,
        domain-E, and surface-Q review. Source:
        ``notebooks/Native_Masked_Surface_EPR/martinis2022_ribbon_native_mask_hpc_handoff.ipynb``.

    .. grid-item-card:: Public Driven Workflow

        :doc:`notebooks/public_driven_workflow`

        Secondary Resolve/Results example for the Driven report path.

    .. grid-item-card:: Public Eigenmode Workflow

        :doc:`notebooks/public_eigenmode_workflow`

        Secondary Resolve/Results example for Eigenmode reports and material
        provenance.

.. toctree::
    :maxdepth: 1
    :hidden:

    notebooks/public_electrostatic_workflow
    notebooks/public_electrostatic_local_workflow
    notebooks/public_driven_workflow
    notebooks/public_eigenmode_workflow
