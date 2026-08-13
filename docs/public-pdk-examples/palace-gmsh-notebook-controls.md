# Palace/Gmsh Notebook Controls

This page is the public control reference for notebooks that turn layout
semantics into a Gmsh mesh, a Palace configuration, and a local or HPC handoff.
It explains reusable controls only. Component selectors, dimensions, private
run paths, accounts, project identifiers, and design-specific values belong in
the consuming private project.

## Notebook sections

Use the same visible sections in every Palace/Gmsh notebook:

| Section | Public controls and review question |
| --- | --- |
| **Design / Geometry** | Which public fixture or caller-supplied component, layer stack, problem type, terminal/interface selectors, and SGB route define the physical model? |
| **Meshing** | Which initial mesh sizes and semantic physical groups are sent to Gmsh, and what AMR DOF ceiling is sent to Palace? |
| **Solver** | Which Palace problem, polynomial order, AMR controls, linear-solver controls, and output fields are requested? |
| **Execution** | Which named profile resolves the executable and resources, and is the notebook generating a handoff, running locally, or analyzing an existing run? |
| **Output / Run Identity** | Which run id, output directory, config, mesh, archive, and source revisions identify this attempt? |
| **Validation / Failure** | Did geometry, physical-group, config-schema, handoff, and result checks pass? Missing or ambiguous required identities fail before execution. |
| **Data Classification / Provenance** | Which records are public, project-internal, or private, and which source, config, mesh, profile, executable version, and checksums produced them? |

The notebook is a readable control surface, not a second implementation.
`semantic_geometry_builder` owns Route A/B geometry identity, `gsim` owns
mesh/config/run/handoff behavior, and OrPen owns public fixtures and examples.

## Design and geometry

Bind the following before meshing:

- component or caller-supplied layout identity;
- PDK and layer-stack identity;
- Palace problem type;
- terminal, conductor, interface, and exterior-boundary selectors;
- SGB route and its semantic sidecar.

SGB Route A represents thin-film metal as sheets. Route B places a closed PEC
boundary shell around an excluded, non-solution conductor interior: the metal
interior receives no volume tetrahedra and is not solved. Stable SGB surface
and provenance identities bind that shell. The route is a declared geometry
contract, not a fallback: changing it changes the physical-group representation
and must be recorded in provenance. See [Semantic Geometry Builder](../features/semantic-geometry-builder.qmd)
and [CAD/XAO Metadata Handoff](../features/cad-xao-metadata-handoff.md).

| Control | Accepted shape or options | Meaning and cost/failure effect |
| --- | --- | --- |
| `COMPONENT_ID` | Consumer-owned stable string | Identifies the source component in run and provenance records; missing or ambiguous identity fails before geometry generation. |
| `COMPONENT_PARAMETERS` | Consumer-owned mapping accepted by its component factory | Defines the instantiated geometry. Parameter validity remains with the factory; geometry size and complexity affect mesh cost. |
| `TERMINAL_PORTS` | Consumer-owned mapping from logical terminals to component port names | Binds Palace terminals to physical ports. Missing or duplicate selectors fail terminal validation. |
| `STACK_MODE` | Scene-helper-validated mode; consult the scene API | Chooses the stack representation. Changing it changes geometry and provenance. |
| `ACTIVE_DIES` | Non-empty sequence of registered die identifiers | Selects participating dies. Unknown or incompatible identifiers fail scene construction. |
| `INTER_DIE_METAL_GAP_UM` | Positive length in micrometres, helper validated | Sets the metal-to-metal separation used by the scene; it is a consumer-owned geometry input. |
| `VACUUM_Z_EXTENT_UM` | Two non-negative micrometre extents, below and above | Sizes the vertical vacuum region; larger extents generally increase volume-mesh cost. |
| `SCENE_MARGIN_X_UM`, `SCENE_MARGIN_Y_UM` | Non-negative micrometre lengths | Extend the lateral scene boundary; larger margins generally increase volume-mesh cost. |
| `SURFACE_EPR_ROUTE` | `"A"` or `"B"` | Selects thin-film sheets or the closed PEC boundary-shell representation described above. |
| `SURFACE_EPR_INTERFACES` | SGB/helper-validated interface mapping | Binds stable interface and face identities; missing or incompatible surfaces fail geometry/config validation. |
| `MATERIAL_OVERLAY` | Material-schema-validated mapping | Supplies material/interface properties without redefining geometry; invalid records fail config generation or schema validation. |

## Meshing

The initial Gmsh mesh and the Palace adaptive mesh are separate controls.
Gmsh controls the first mesh and its semantic physical groups. Palace
`Model.Refinement` controls solution-driven adaptive mesh refinement (AMR)
after that mesh is loaded.

- `MaxIts` is an upper bound on AMR iterations, not a required count.
- `Tol` can stop refinement before `MaxIts` when the estimator target is met.
- `MaxSize` is the maximum number of degrees of freedom (DOFs) allowed during
  refinement.
- `UpdateFraction` is the Dörfler marking fraction. Larger values mark more
  elements per iteration, usually increasing work per AMR step.

More iterations, a tighter tolerance, a larger update fraction, and a larger
AMR DOF ceiling all tend to increase memory or runtime; none is a universal
convergence setting. The official reference is Palace 0.16.1
[`Model.Refinement`](https://awslabs.github.io/palace/v0.16.1/config/model/#model%5B%22Refinement%22%5D).

| Control | Accepted shape or options | Meaning and cost/failure effect |
| --- | --- | --- |
| `MESH_PRESET` | `"coarse"`, `"default"`, or `"fine"` | Selects a coherent initial Gmsh policy. Unknown presets fail helper validation. |
| `REFINED_MESH_SIZE_UM` | `None` or a positive explicit size in micrometres | `None` delegates refined sizing to auto-size controls; an explicit smaller size normally increases element count. |
| `MAX_MESH_SIZE_UM` | Positive size in micrometres | Caps initial element size; a smaller cap normally increases element count. This is distinct from Palace's AMR DOF ceiling. |
| `PLANAR_CONDUCTORS` | Boolean | Selects the helper's planar-conductor treatment; it must agree with the chosen SGB representation. |
| `AUTO_SIZE_MESH` | Boolean | Enables feature-derived sizing. When disabled, explicit mesh sizes must provide a complete valid policy. |
| `CELLS_PER_SMALLEST_FEATURE` | Positive integer, helper validated | Controls feature-derived resolution; larger values normally increase element count and memory. |
| `SHOW_GMSH_GUI` | Boolean | Opens the interactive Gmsh viewer when the environment supports it; headless runs keep it disabled. |

## Solver

`Solver.Order` is the finite-element polynomial degree. For Electrostatic
problems, Palace's Laplace operator constructs an MFEM `H1_FECollection` with
this order, so `Order = 2` selects a quadratic H1 basis. It is broadly
analogous to a second-order FEM basis, but it is not a one-to-one HFSS mesh
order setting.

Keep these control families distinct:

- `Solver.Order`: approximation order;
- `Model.Refinement.*`: adaptive mesh iteration and marking policy;
- `Solver.Linear.Tol` and `Solver.Linear.MaxIts`: linear-system stopping
  controls.

See the official Palace 0.16.1
[solver](https://awslabs.github.io/palace/v0.16.1/config/solver/) and
[model](https://awslabs.github.io/palace/v0.16.1/config/model/) references.

| Control | Accepted shape or options | Meaning and cost/failure effect |
| --- | --- | --- |
| `PALACE_CONFIG_VERSION` | Supported schema-version string | Records the writer target. Unsupported versions fail config/schema validation. |
| `FINITE_ELEMENT_ORDER` | Positive integer accepted by Palace | Sets `Solver.Order`; higher order increases per-element work and memory. No value is a universal default. |
| `REFINEMENT_MAX_ITS` | Non-negative integer accepted by Palace | Maximum AMR iterations, not a required count; larger limits permit more refinement work. |
| `REFINEMENT_TOL` | Positive estimator tolerance accepted by Palace | May stop AMR early when met; tighter values can increase iterations and DOFs. |
| `REFINEMENT_UPDATE_FRACTION` | Number strictly between `0` and `1` | Larger Dörfler fractions mark more elements per AMR step and normally increase step cost. |
| `LINEAR_SOLVER_TOL` | Positive solver tolerance accepted by Palace | Controls linear residual stopping; tighter values can increase iterations. |
| `LINEAR_SOLVER_MAX_ITS` | Positive integer accepted by Palace | Bounds linear iterations; exhaustion without convergence is a solver failure. |
| `SAVE_ELECTROSTATIC_FIELDS` | Non-negative integer accepted by Palace | Sets the number of electrostatic field solutions to save; larger values increase output size and I/O. |

## Schema and runtime versions

The current `gsim` writer targets the Palace 0.16.0 configuration schema.
Palace 0.16.1 changes only boundary-validation constraints relative to 0.16.0;
the solver and refinement fields described here are unchanged. Every consuming
configuration must still be validated against the schema of its actual Palace
runtime.

Schema compatibility does not prove numerical convergence or successful
execution. Record the writer schema target and the actual runtime version as
separate provenance fields.

## Execution and profiles

A named profile resolves the Palace executable and resource request. For F1,
the active profile selects a direct Palace 0.16.1 executable at a profile-owned
path; this workflow has no Spack route. Never copy profile-owned paths,
accounts, hostnames, or allocation identifiers into public docs.

Generate `config.json` once, validate it, and package that exact file. If a
notebook patches a run-local config, package with
`generate_handoff_package(write_config=False)` so packaging cannot overwrite
the reviewed config. See [Palace Config Generation](../features/palace-config-generation.md),
[Native Masked Surface EPR Handoff](../features/native-masked-surface-epr-handoff.md),
and [Problem Notebooks](problem-notebooks.md).

| Control | Accepted shape or options | Meaning and cost/failure effect |
| --- | --- | --- |
| `WORKFLOW_ACTION` | Exactly `"prepare_handoff"` or `"analyze_handoff"` | Generates a new handoff or reads an existing run. Any other value fails before execution. |
| `HPC_PROFILE` | Registered profile identifier | Resolves executable and site policy. Unknown or unavailable profiles fail resolution; profile contents remain outside public docs. |
| `HPC_RESOURCE_OVERRIDES` | Mapping of positive-integer `nodes`, `num_processes`, and `num_threads`, validated by the profile/helper | Overrides reusable resource requests. Larger requests can raise scheduling and runtime cost; invalid combinations fail profile validation. |
| `SBATCH_JOB_NAME` | Profile/helper-valid scheduler job-name string | Gives the handoff a traceable scheduler label; invalid names fail script generation or submission. |

## Output and run identity

| Control | Accepted shape or options | Meaning and cost/failure effect |
| --- | --- | --- |
| `RUN_ID` | Stable non-empty run identifier | Names one prepare/analyze attempt and its receipts. Reusing an identity for different bytes makes provenance ambiguous. |
| `RUN_ROOT` | Writable path for the prepared run | Owns generated mesh, config, handoff, and receipts; a missing or unwritable location fails preparation. |
| `ANALYSIS_RUN_ROOT` | Existing prepared/result path | `analyze_handoff` must point to the same `RUN_ID` produced by `prepare_handoff`; missing or mismatched identity fails closed. |

## Validation and failure

| Control | Accepted shape or options | Meaning and cost/failure effect |
| --- | --- | --- |
| `EXPECTED_GSIM_VERSION` | Exact version string | Prevents a notebook from silently running against a different helper contract. |
| `VALIDATE_MESH` | Boolean | Enables semantic mesh and physical-group checks; disabling it removes that diagnostic and does not make an invalid mesh acceptable. |
| `VALIDATE_PALACE_SCHEMA` | Boolean | Validates the generated config against the selected Palace schema before handoff. |
| `INCLUDE_HANDOFF_HASHES` | Boolean | Adds content hashes to the handoff manifest; enabling it adds small hashing cost and strengthens byte identity. |

## Data classification and provenance

| Control | Accepted shape or options | Meaning and cost/failure effect |
| --- | --- | --- |
| `DATA_CLASSIFICATION` | Policy-controlled classification label; consult the owning project | Determines allowed consumers and storage/publication boundaries. An unknown label fails policy review. |
| `PUBLICATION_INTENT` | Policy-controlled intent label; consult the owning project | Records whether publication is requested; it never grants publication authority by itself. |
| `PROVENANCE` | Structured mapping of source, geometry/route, config/schema, profile/runtime, run, classification, and revision identities | Travels with handoff metadata so results can be traced. Missing required identities make the handoff non-auditable. |

A reviewable handoff binds at least:

- source component, stack, route, selectors, and source revisions;
- semantic sidecar, mesh, config, schema target, and runtime version;
- profile id without public disclosure of private profile contents;
- run/output identity, archive manifest, and checksums;
- geometry, physical-group, schema, handoff, and result validation status;
- data classification and allowed publication surface.

Missing physical groups, terminals, selectors, executable identity, or a
schema-valid configuration is a technical failure. A valid handoff is not
evidence of mesh convergence, solver convergence, or scientific acceptance.
