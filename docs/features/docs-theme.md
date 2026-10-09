# Documentation theme and toolchain

This site uses the public `askr-html` format from
[Askr v0.8.0 released source](https://github.com/arfiligol/askr/tree/v0.8.0).
The unchanged extension is
vendored at `docs/_extensions/arfiligol/askr`, including its MIT license,
third-party notices and local font/icon assets. The extension manifest
`_extension.yml` declares version `0.8.0` and Quarto `>=1.9.38 <1.11`.
The [released extension metadata](https://github.com/arfiligol/askr/blob/v0.8.0/_extensions/askr/_extension.yml)
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
quarto add arfiligol/askr@v0.8.0 --no-prompt
```

Commit reviewed extension updates as consumer bytes; do not edit the installed
copy or track a moving branch. `_quarto.yml` selects `askr-html` without
replacing its themes, reading measure, fonts, colors or native controls.
`styles.css` retains only local table overflow and diagram popout behavior.
Its consumer-only color aliases follow Askr's `--qdk-border` and `--qdk-canvas`
tokens. The [Cells gallery](../public-pdk-examples/index.md#components-layout)
uses the stock inline Image Viewer; the previous custom iframe viewer is retired.
See the [released viewer usage](https://github.com/arfiligol/askr/blob/v0.8.0/usage/image-viewer.qmd).

Documentation rendering has `execute.enabled: false`: it publishes saved
notebook content, not fresh simulations. The normal documentation prerequisites
and existing Python docs dependency cohort remain unchanged. Theme/render
success is not source-layout validation, native mesh/contact/solver evidence,
or acceptance of scientific results.
