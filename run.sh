#!/usr/bin/env bash
# Print a summary table of the Charades labels.
#
# Usage:
#   ./run.sh                    # summary table (first 20 videos)
#   ./run.sh --limit 50
#   ./run.sh --id YSKX3         # full labels for one video
#   ./run.sh --test             # run the unit tests
set -euo pipefail
cd "$(dirname "$0")"

source scripts/find_python.sh
find_python

if [[ "${1:-}" == "--test" ]]; then
  exec "$PYTHON" -m unittest discover -s tests -t . -v
fi

exec "$PYTHON" -m explorer.cli "$@"
