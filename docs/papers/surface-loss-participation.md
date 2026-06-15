# Surface Loss And Participation Studies

**Design family:** analysis method

**Status:** source selection

Collect public studies that define useful targets for surface participation,
surface-Q mapping, dielectric loss attribution, and report validation.

No private NCUAS preset names, private material values, unpublished fitting
results, or private run evidence belong on this page. This page is the public
source queue used before any MA/MS/SA preset becomes part of the PDK contract.

## Preset Review Fields

Before a source can populate `orpen_sc_pdk.tech.interface_preset_records`, the
review must identify:

- interface role: `MA`, `MS`, `SA`, bulk substrate, or another explicit role;
- geometry family: CPW resonator, transmon, flip-chip package, or other;
- extracted fields: thickness, dielectric constant or material record,
  loss tangent, and whether each field is measured, fitted, assumed, or
  scaled;
- material/process assumptions: metal, substrate, surface treatment, trenching,
  oxide, temperature, and frequency range when available;
- default-selection scope: whether the source supports public defaults or only
  a caller-selected preset;
- reusable handoff: whether the record should be represented in
  `orpen-sc-pdk`, `gsim`, or only in downstream private workflows.

## Candidate Sources

| Source | Candidate use | Review status |
|---|---|---|
| Wenner et al., "Surface loss simulations of superconducting coplanar waveguide resonators," Applied Physics Letters 99, 113513 (2011), [doi:10.1063/1.3637047](https://doi.org/10.1063/1.3637047) | Defines the CPW `MA`/`MS`/`SA` interface taxonomy used by many surface-loss workflows and is suitable for validating role naming, scaling checks, and report interpretation. | Keep as taxonomy/reference first; do not turn its example assumptions into public defaults without an explicit process match. |
| Woods et al., "Determining Interface Dielectric Losses in Superconducting Coplanar-Waveguide Resonators," Physical Review Applied 12, 014012 (2019), [doi:10.1103/PhysRevApplied.12.014012](https://doi.org/10.1103/PhysRevApplied.12.014012) | Candidate source for extracted `MA`, `MS`, `SA`, and substrate-loss values in CPW resonators after the public material/process assumptions are reviewed. | Primary candidate for source-backed preset extraction; values still need a public review table and tests before entering the PDK table. |
| Wang et al., "Surface participation and dielectric loss in superconducting qubits," Applied Physics Letters 107, 162601 (2015), [doi:10.1063/1.4934486](https://doi.org/10.1063/1.4934486) | Useful for transmon surface-participation validation and geometry-dependent report checks. | Candidate validation target, not a direct CPW preset default. |
| Lahtinen and Mottonen, "Effects of device geometry and material properties on dielectric losses in superconducting coplanar-waveguide resonators," Journal of Physics: Condensed Matter 32, 405702 (2020), [doi:10.1088/1361-648X/ab98c8](https://doi.org/10.1088/1361-648X/ab98c8) | Useful for uncertainty-aware CPW resonator material/loss interpretation and inverse-problem style validation. | Candidate for provenance and uncertainty schema design, not a default preset. |

## Public Preset Gate

The public PDK can accept an interface preset only after:

1. the candidate source is listed above or in another public review page;
2. the record has a non-empty source/provenance string;
3. the role mapping is explicit and matches `gsim` `DielectricInterfaceSpec`
   semantics;
4. the record uses either a public material name or explicit permittivity;
5. tests prove the record validates through
   `validate_interface_preset_records()` and can be handed to `gsim` without
   adding PDK-owned Palace runtime logic;
6. any automatic default-selection rule is documented separately from the
   caller-supplied preset table.

Related issue:

- {doc}`../issues/source-backed-interface-presets`
