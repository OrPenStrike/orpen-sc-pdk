# Documentation theme and toolchain

This site uses the public `askr-html` format from
[Askr v0.7.0 released source](https://github.com/arfiligol/askr/tree/b79fec30ff7b256ab07170c7c338b9e488d38fae).
The unchanged extension is
vendored at `docs/_extensions/arfiligol/askr`, including its MIT license,
third-party notices and local font/icon assets. The extension manifest
`_extension.yml` declares version `0.7.0` and Quarto `>=1.9.38 <1.11`.
The [released extension metadata](https://github.com/arfiligol/askr/blob/b79fec30ff7b256ab07170c7c338b9e488d38fae/_extensions/askr/_extension.yml)
records the format and compatibility requirements.

The root `_extensions` symlink points to `docs/_extensions`. It lets relative
extension includes resolve through the existing `docs/notebooks` symlink when
rendering saved notebooks. There is one vendored extension, not a second copy;
canonical notebook source, pairing and outputs are unchanged.

Use Quarto **1.10.19**, the selected stable consumer/CI toolchain. Install that
version from the [official release](https://github.com/quarto-dev/quarto-cli/releases/tag/v1.10.19),
then check `quarto --version`. To reproduce the extension installation:

```bash
cd docs
quarto add arfiligol/askr@v0.7.0 --no-prompt
```

Commit reviewed extension updates as consumer bytes; do not edit the installed
copy or track a moving branch. `_quarto.yml` selects `askr-html` without
replacing its themes, reading measure, fonts, colors or native controls.
`styles.css` and `layout-viewer.css` retain only local table overflow, diagram
popout behavior and the static viewer frame. Their consumer-only color aliases
follow Askr's `--qdk-border` and `--qdk-canvas` tokens.

Documentation rendering has `execute.enabled: false`: it publishes saved
notebook content, not fresh simulations. The normal documentation prerequisites
and existing Python docs dependency cohort remain unchanged. Theme/render
success is not source-layout validation, native mesh/contact/solver evidence,
or acceptance of scientific results.
