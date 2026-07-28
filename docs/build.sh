#!/usr/bin/env bash
# Regenerates SRS.docx from SRS.md. Run after editing SRS.md.
set -euo pipefail
cd "$(dirname "$0")"

pandoc -f markdown-implicit_figures SRS.md -o SRS.docx --resource-path=.

echo "Built docs/SRS.docx"
