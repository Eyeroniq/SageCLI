#!/usr/bin/env bash
# Download the Phi-3 Mini 4k Instruct Q4 GGUF model into ./models/ (resumable).
#
# The model is NOT part of this repository and has its own license
# (see https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf).
#
# Usage:  bash scripts/download_model.sh [target_dir]
set -euo pipefail

REPO="microsoft/Phi-3-mini-4k-instruct-gguf"
FILE="Phi-3-mini-4k-instruct-q4.gguf"
URL="https://huggingface.co/${REPO}/resolve/main/${FILE}"
TARGET_DIR="${1:-models}"
TARGET="${TARGET_DIR}/${FILE}"

mkdir -p "${TARGET_DIR}"

echo "Downloading ${FILE}"
echo "  from ${URL}"
echo "  to   ${TARGET}"

if command -v curl >/dev/null 2>&1; then
    # -C - resumes a partial download; --fail stops on HTTP errors.
    curl --fail --location --continue-at - --output "${TARGET}" "${URL}"
elif command -v wget >/dev/null 2>&1; then
    wget --continue --output-document="${TARGET}" "${URL}"
else
    echo "Error: neither curl nor wget is installed." >&2
    exit 1
fi

echo "Done. Size: $(du -h "${TARGET}" | cut -f1)"
echo "Run:  sage --model \"${TARGET}\" \"list files in this folder\""
