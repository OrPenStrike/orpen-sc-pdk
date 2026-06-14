# Private Static Mount Tests

**Repo:** `orpen-sc-pdk`

Public tests should verify the static private mount contract without importing
the real private layout repo.

Required checks:

- no private mount is a no-op;
- a fake mounted package with `__all__` can re-export cells;
- mounted private cross-sections can be merged into the PDK registry;
- helper functions do not become GF+ cells.

Related feature:

- {doc}`../features/private-static-mount`
