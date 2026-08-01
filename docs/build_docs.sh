#!/usr/bin/env bash
# Builds the final SRS, the midterm report, or both from Markdown to DOCX.
set -euo pipefail

cd "$(dirname "$0")"

for command_name in pandoc python3; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Error: required command '$command_name' is not installed." >&2
    exit 1
  fi
done

build_document() {
  local source_file="$1"
  local output_file="$2"
  local temporary_file="${output_file%.docx}.new.docx"

  if [[ ! -f "$source_file" ]]; then
    echo "Error: docs/$source_file was not found." >&2
    exit 1
  fi

  pandoc \
    --from=markdown+implicit_figures+fenced_divs+bracketed_spans \
    --to=docx \
    --resource-path=. \
    --lua-filter=pagebreaks.lua \
    "$source_file" \
    --output="$temporary_file"

  python3 postprocess_docx.py "$temporary_file"
  mv "$temporary_file" "$output_file"

  echo "Built docs/$output_file from docs/$source_file"
}

target="${1:-all}"

case "$target" in
  final)
    build_document "SRS.md" "SRS.docx"
    ;;
  mid)
    build_document "srs_mid.md" "srs_mid.docx"
    ;;
  all)
    build_document "SRS.md" "SRS.docx"
    build_document "srs_mid.md" "srs_mid.docx"
    ;;
  *)
    echo "Usage: $0 [final|mid|all]" >&2
    exit 2
    ;;
esac
