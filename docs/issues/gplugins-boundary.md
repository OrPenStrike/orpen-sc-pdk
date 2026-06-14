# GDSFactory Plugin Boundary

**Repo:** `gplugins`

Generic plugin helpers should not be duplicated in the PDK. Move reusable
plugin integration into `gplugins`; keep only PDK-specific material, layer, and
GF+ import semantics in `orpen-sc-pdk`.
