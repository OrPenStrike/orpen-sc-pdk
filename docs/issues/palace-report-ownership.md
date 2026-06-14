# Palace Report Ownership

**Repo:** `gsim`

Reusable Palace report generation should live upstream instead of in a private
layout repo or inside the PDK core.

Problem:

- private notebooks already parse Palace indexed reports such as
  `domain-E.csv`, `surface-Q.csv`, and `port-EPR.csv` back to physical names;
- those mappings must come from generated solver artifacts, not notebook-local
  physical-name scans or private layout naming rules;
- the PDK should not own a parallel report framework when `gsim` already owns
  Palace result loading.

Proposed path:

- extend `gsim.palace.results` so reusable report loaders can consume
  `palace_index_map.json`;
- keep public PDK examples focused on producing solver artifacts and reading
  public-safe reports through `gsim`;
- keep richer report tables and presentation layers downstream of a reusable
  `gsim` result schema.

Verified local changes:

- `gsim` commit `5caa2db`: adds `load_postprocessing_index_map()` and
  `load_indexed_csv()` to the public `gsim.palace` surface;
- `load_indexed_csv()` can load indexed Palace CSV files, infer standard
  sections for `domain-E.csv`, `surface-Q.csv`, and `port-EPR.csv`, rename
  indexed columns with physical names from `palace_index_map.json`, and expose
  JSON-friendly column provenance rows;
- focused `gsim` tests cover directory sources, results-dict sources,
  domain-energy mapping, surface-Q mapping, unmapped index preservation, Ruff,
  and targeted Pyright.

Remaining slices:

- add electrostatic capacitance matrix loaders that consume
  `Boundaries.Terminal` rows from `palace_index_map.json`;
- run real Palace coarse-solve smoke checks when a Palace binary is available
  on the local machine;
- build higher-level EPR/surface-Q summary frames on top of the indexed CSV
  loader instead of copying private report code.

Related features:

- {doc}`../features/palace-reporting`
- {doc}`../features/benchmark-cost-analysis`
