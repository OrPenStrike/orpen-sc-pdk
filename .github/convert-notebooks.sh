#!/usr/bin/env bash
set -euo pipefail

source_dir="${1:-notebooks/src}"
output_dir="${2:-notebooks}"
action="${3:---check}"

case "${action}" in
  --check)
    uv run --group docs python scripts/sync_qmd_notebooks.py "${source_dir}" "${output_dir}"
    ;;
  --generate)
    uv run --group docs python scripts/sync_qmd_notebooks.py \
      "${source_dir}" "${output_dir}" --generate
    ;;
  *)
    echo "Usage: $0 [source-dir] [output-dir] [--check|--generate]" >&2
    exit 2
    ;;
esac
