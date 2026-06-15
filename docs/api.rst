:orphan:

###
API
###

.. automodule:: orpen_sc_pdk
    :members:

.. automodule:: orpen_sc_pdk.cells
    :members:

.. automodule:: orpen_sc_pdk.materials
    :members:

Technology modules such as ``orpen_sc_pdk.tech`` remain importable for PDK
activation and layer-stack construction. They intentionally are not expanded
with ``:members:`` here because notebook-facing material access should go
through copy-returning helpers in ``orpen_sc_pdk.materials`` rather than raw
mutable technology records.

.. automodule:: orpen_sc_pdk.tech
