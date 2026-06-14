# Static Private Layout Mount

**Target:** `orpen-sc-pdk`

**Status:** optional local bridge

The primary GF+ route is to open the private repo as the active GF+ project and
use `orpen-sc-pdk` as its base PDK. A public-PDK ignored mount remains available
only for local experiments that need private source below the public checkout.

Private layout packages should expose GF cells through explicit imports and
`__all__`. The public PDK only re-exports those cells when the local environment
sets the private mount variables.

Acceptance direction:

- `orpen_sc_pdk/cells/privates/*` remains ignored and private source is not
  tracked by the public PDK;
- `orpen_sc_pdk.cells` remains importable when no private mount exists;
- when the private mount exists and `ORPEN_SC_PDK_PRIVATE_LAYOUT_REPO`,
  `ORPEN_SC_PDK_PRIVATE_LAYOUT_CELLS`, and
  `ORPEN_SC_PDK_PRIVATE_LAYOUT_XSECTIONS` are set, representative private
  cells appear in the GF+ Component List;
- private cells consume public `LAYER`, `LAYER_STACK`, and `LAYER_VIEWS`
  semantics from `orpen-sc-pdk`.
