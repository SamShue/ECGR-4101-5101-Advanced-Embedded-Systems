#!/usr/bin/env bash
# Builds each version of the Startup Process and Bootloaders quiz and merges
# them (A, then B) into one collated PDF for printing.
set -euo pipefail
cd "$(dirname "$0")"

QUIZ="quiz_bootloaders"
VERSIONS=(versionA versionB)
OUT="${QUIZ}_combined.pdf"

pdfs=()
for v in "${VERSIONS[@]}"; do
    echo "Building ${v}..."
    latexmk -pdf -interaction=nonstopmode -halt-on-error -cd "${v}/${QUIZ}.tex" >/dev/null
    pdfs+=("${v}/${QUIZ}.pdf")
done

echo "Merging into ${OUT}..."
pdfunite "${pdfs[@]}" "${OUT}"
echo "Done: ${OUT}"
