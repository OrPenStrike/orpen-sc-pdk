# GDSFactory Plugin Boundary

**Repo:** `gplugins`

Generic plugin helpers should not be duplicated in the PDK. Move reusable
plugin integration into `gplugins`; keep only PDK-specific material, layer, and
GF+ import semantics in `orpen-sc-pdk`.

Problem:

- `gplugins` already contains legacy Palace helpers for capacitance and
  scattering workflows, plus generic meshwell adapters;
- the SCQ simulation inventory now needs material overlays, role-aware mesh
  manifests, Palace config generation, report bundles, and local/cloud runtime
  evidence;
- duplicating those solver-specific contracts in both `gsim` and `gplugins`
  would create two public Palace runtimes.

Boundary decision:

- `gsim` owns Palace problem models, config generation, material resolution,
  report parsing, run summaries, and local/cloud execution metadata;
- `meshwell` owns reusable CAD/mesh construction and physical-name conventions;
- `orpen-sc-pdk` owns public PDK layer/material/cell metadata consumed by the
  solver workflows;
- `gplugins` may keep or add thin compatibility wrappers only when they delegate
  to the reusable `gsim` surface and do not reimplement solver internals.

Current local evidence:

- local `gplugins` branch `feature/palace-meshwell-gap-tracking` exposes
  `gplugins.palace.run_capacitive_simulation_palace()` and
  `gplugins.palace.run_scattering_simulation_palace()`;
- those helpers generate Palace JSON from gplugins-local templates, call a
  `palace` executable from `PATH`, and read raw Palace CSV outputs directly;
- the current `gsim` local branch already owns the richer SCQ-relevant path:
  role/index artifacts, material-resolution provenance, composed
  Driven/Eigenmode/Electrostatic report bundles, and reusable run summaries.
- the NCUAS handoff inventory also points to `gsim` for future Slurm/Sbatch,
  handoff archive, site/profile, and resource-record schemas; adding those to
  the older `gplugins.palace` wrappers would duplicate the Palace runtime.

Proposed path:

- do not port NCUAS or OrPen SCQ Palace helpers into `gplugins.palace` as new
  core logic;
- if a public compatibility layer is needed, add `gplugins` wrappers that call
  `gsim.palace` APIs and keep the legacy gplugins function names shallow;
- wrapper tests should compare generated public OrPen fixture artifacts against
  the same `gsim` summary/report APIs, not against private notebooks or
  gplugins-local JSON templates;
- keep `gplugins` docs explicit that Palace workflow ownership for this
  ecosystem is `gsim`, while `gplugins` remains a generic plugin façade.
- do not add HPC profile catalogs, sbatch renderers, handoff archives, or
  benchmark/resource record schemas to `gplugins.palace`; those belong to
  `gsim.palace` when they become reusable.

Acceptance checks:

- no PDK-specific material names, layer semantics, or private physical-name
  assumptions are added to `gplugins`;
- no duplicated Palace config/report/runtime implementation appears in
  `gplugins`;
- any new `gplugins.palace` entrypoint can run against public OrPen examples
  through editable `gsim` and produces the same reusable summary/report
  artifacts.

Related issue:

- {doc}`palace-api-responsibility-boundary`
