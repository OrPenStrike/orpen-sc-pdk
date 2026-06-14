# Material Database Overlay

**Target:** `orpen-sc-pdk` and `gsim`

**Status:** candidate

SCQ material records should live in the PDK. Reusable material resolution,
frequency evaluation, and Palace material translation should live in `gsim`.

The integration should preserve `materials.json` style data sources when they
are introduced, rather than treating them as generated artifacts.
