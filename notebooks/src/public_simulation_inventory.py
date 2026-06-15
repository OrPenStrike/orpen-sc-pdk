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
# # Public Simulation Inventory
#
# This notebook displays the publication-safe simulation inventory used to
# compare private NCUAS Palace/AEDT notebooks with public OrPen and `gsim`
# workflow surfaces. It keeps private layouts, private run artifacts, and
# notebook-local helper implementations out of the public notebook.

# %%
from IPython.display import display

from scripts.public_palace_smoke_evidence import (
    load_public_gsim_boundary_review_crosscheck,
    load_public_interface_preset_review_queue,
    load_public_problem_notebook_crosscheck,
    load_public_simulation_goal_audit,
    load_public_simulation_helper_node_inventory,
    public_cad_mesh_identity_handoff_table,
    public_gsim_boundary_review_crosscheck_table,
    public_interface_preset_candidate_review_table,
    public_interface_preset_promotion_gate_table,
    public_interface_preset_source_review_table,
    public_problem_notebook_crosscheck_table,
    public_simulation_goal_audit_table,
    public_simulation_helper_node_inventory_table,
    public_thin_film_sheet_proxy_interface_table,
)

# %% [markdown]
# ## Helper-node inventory
#
# Helper nodes describe why a reusable simulation function exists, where it
# should live in the GDSFactory ecosystem, and which public issue tracks the
# remaining evidence.

# %%
helper_node_inventory = public_simulation_helper_node_inventory_table()

display(helper_node_inventory)

# %% [markdown]
# ## Representative notebook cross-check
#
# The cross-check keeps one private representative notebook per primary
# problem type visible without copying private cells, private paths, or saved
# outputs into public examples.

# %%
problem_notebook_crosscheck = public_problem_notebook_crosscheck_table()

display(problem_notebook_crosscheck)

# %% [markdown]
# ## Goal-level audit
#
# The goal audit separates covered public evidence from opt-in solver replay
# requirements and explicitly deferred scope. This keeps notebook review tied
# to the migration objective instead of only showing feature tables.

# %%
goal_audit = public_simulation_goal_audit_table()

display(goal_audit)

# %% [markdown]
# ## Gsim boundary review cross-check
#
# The cross-check maps the current local `gsim` Palace branch commits to
# responsibility-boundary review groups. It is traceability evidence only: some
# commits are directly exercised by public notebooks, while runtime, cloud,
# handoff, and API-documentation commits are covered through reusable `gsim`
# evidence surfaces or owner-module import rules.

# %%
gsim_boundary_review = public_gsim_boundary_review_crosscheck_table()

display(gsim_boundary_review)

# %% [markdown]
# ## CAD/mesh identity handoff
#
# CAD/mesh identity evidence stays notebook-visible as consumer evidence. The
# table consumes generated `mesh_manifest.json`, `palace_index_map.json`, and
# `config.json` artifacts for the public Driven, Eigenmode, and Electrostatic
# fixtures; upstream physical-name grammar and backend equivalence remain owned
# by `meshwell`, while Palace index/report lookup remains owned by `gsim`.

# %%
cad_mesh_identity_handoff = public_cad_mesh_identity_handoff_table()

display(cad_mesh_identity_handoff)

# %% [markdown]
# ## Interface preset source review
#
# MA/MS/SA candidate values stay in a source-review queue until accepted public
# records, process scope, and default-selection rules exist. These tables are
# notebook-visible promotion-gate evidence, not public defaults.

# %%
interface_preset_queue = load_public_interface_preset_review_queue()
interface_preset_sources = public_interface_preset_source_review_table()
interface_preset_candidates = public_interface_preset_candidate_review_table()

display(interface_preset_sources)
display(interface_preset_candidates)

# %% [markdown]
# ## Interface preset promotion gate
#
# Candidate MA/MS/SA rows are review evidence, not public defaults. The gate
# table records which acceptance decisions are still missing before any row can
# populate `tech.interface_preset_records` or become automatic notebook policy.

# %%
interface_preset_promotion_gate = public_interface_preset_promotion_gate_table()

display(interface_preset_promotion_gate)

# %% [markdown]
# ## Thin-film sheet proxy evidence
#
# The source-backed preset gate also needs evidence for conductor-sheet
# interfaces that produce separate caller-supplied MA and MS proxy rows. This
# table uses public material-kind data and `gsim` postprocessing builders; it is
# still fixture-only evidence, not automatic public defaults.

# %%
thin_film_proxy_interfaces = public_thin_film_sheet_proxy_interface_table()

display(thin_film_proxy_interfaces)

# %% [markdown]
# ## Coverage summary
#
# The summary groups the public inventory by coverage status, intended
# ecosystem home, goal-audit status, boundary-review status, and owning issue.

# %%
display(
    {
        "helper_node_count": len(load_public_simulation_helper_node_inventory()),
        "crosscheck_row_count": len(load_public_problem_notebook_crosscheck()),
        "goal_audit_row_count": len(load_public_simulation_goal_audit()),
        "gsim_boundary_review_row_count": len(load_public_gsim_boundary_review_crosscheck()),
        "cad_mesh_identity_problem_count": len(cad_mesh_identity_handoff),
        "interface_preset_source_count": len(interface_preset_queue["sources"]),
        "interface_preset_candidate_count": len(interface_preset_queue["candidate_records"]),
        "interface_preset_promotion_gate_count": len(interface_preset_promotion_gate),
        "thin_film_proxy_interface_count": len(thin_film_proxy_interfaces),
        "coverage_status_counts": problem_notebook_crosscheck["coverage_status"]
        .value_counts(sort=False)
        .to_dict(),
        "goal_status_counts": goal_audit["current_status"].value_counts(sort=False).to_dict(),
        "boundary_group_counts": gsim_boundary_review["boundary_group"]
        .value_counts(sort=False)
        .to_dict(),
        "boundary_review_status_counts": gsim_boundary_review["review_status"]
        .value_counts(sort=False)
        .to_dict(),
        "ecosystem_home_counts": helper_node_inventory["gdsfactory_home"]
        .value_counts(sort=False)
        .to_dict(),
        "issue_counts": helper_node_inventory["next_issue"].value_counts(sort=False).to_dict(),
    }
)
