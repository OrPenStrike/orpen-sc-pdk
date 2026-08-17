# SCGSim Integration

SCGSim is the sole reusable simulation runtime for OrPen notebooks.

```text
OrPen component + layer stack + material/annotation records
                         |
                         v
        SCGSim SGB Core -> Palace or AEDT backend
                         |
                         v
              handoff -> run -> resolve -> report
```

OrPen owns source design intent and public Notebook UX. Layout ports are named
locators plus sheet geometry; they do not carry Palace L/C/R, mesh profiles, or
AEDT assignment labels. SCGSim owns semantic geometry/topology after layout
ingestion, backend lowering, solver execution contracts, returned-run identity,
and reports. Structured IDs and provenance must survive the complete path;
physical names are labels rather than semantic authority.

Palace configs from `write_config()` always include
`Model.Refinement.Nonconformal`. SCGSim defaults it to `false`. Notebooks may
opt into nonconformal AMR with `set_numerical(amr_nonconformal=True)`. Do not
omit the key or rely on Palace's default `true`.

The dependency groups are backend-specific so users without AEDT do not need
its optional runtime:

```bash
uv sync -p 3.12 --group palace-notebooks
uv sync -p 3.12 --group aedt-notebooks
```

No legacy solver-compatibility package or external geometry-builder checkout is
required by an OrPen consumer.
