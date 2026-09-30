# Sourced by setup.sh and run.sh. Sets $PYTHON to a Python 3.8+ interpreter.
#
# Tries `python3` first, then `python`. Each candidate is actually executed,
# so stubs that exist on PATH but don't work (e.g. the Windows Store alias)
# are skipped.

find_python() {
  local candidate
  for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 &&
       "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' >/dev/null 2>&1; then
      PYTHON="$candidate"
      return 0
    fi
  done
  echo "error: Python 3.8+ is required but was not found on PATH." >&2
  exit 1
}
