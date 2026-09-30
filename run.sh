#!/usr/bin/env bash
# Start the Charades Explorer.
#
# Usage:
#   ./run.sh                      # web UI at http://localhost:8000 (PORT=9000 ./run.sh to change)
#   ./run.sh --cli [options]      # summary table in the terminal (./run.sh --cli --help)
#   ./run.sh --test               # run the unit tests
set -euo pipefail
cd "$(dirname "$0")"

source scripts/find_python.sh
find_python

case "${1:-}" in
  --cli)
    shift
    exec "$PYTHON" -m explorer.cli "$@"
    ;;
  --test)
    exec "$PYTHON" -m unittest discover -s tests -t . -v
    ;;
  *)
    exec "$PYTHON" -m explorer.server "$@"
    ;;
esac
