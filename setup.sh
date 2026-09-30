#!/usr/bin/env bash
# One-time setup: checks for Python 3 and downloads the Charades annotations
# into ./data. No packages are installed; the tool uses only the standard library.
#
# Usage:
#   ./setup.sh                          # download from the official AI2 mirror
#   ./setup.sh --zip ~/Downloads/Charades.zip   # use a zip you downloaded yourself
set -euo pipefail
cd "$(dirname "$0")"

source scripts/find_python.sh
find_python
echo "[setup] using $("$PYTHON" --version 2>&1) ($PYTHON)"

"$PYTHON" scripts/download_data.py "$@"
