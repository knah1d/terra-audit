#!/usr/bin/env bash
# Regenerates SRS.docx from SRS.md. Run after editing SRS.md.
set -euo pipefail
cd "$(dirname "$0")"
output="SRS.docx"
temporary="${output%.docx}.new.docx"
pandoc --from=markdown+implicit_figures+fenced_divs --to=docx --resource-path=. --lua-filter=pagebreaks.lua SRS.md --output="$temporary"
python3 postprocess_docx.py "$temporary"
mv "$temporary" "$output"
echo "Built docs/$output from docs/SRS.md"
