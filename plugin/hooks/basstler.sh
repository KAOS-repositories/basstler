#!/bin/bash
set -euo pipefail

# Runs one module of the basstler package with the package's own interpreter,
# from the project root, once the package is ready to run:
#   "${BASSTLER_PLUGIN_ROOT}/hooks/basstler.sh" <module> [arguments...]
# runs `python -m basstler.<module> [arguments...]`. An install a session
# start is still running is waited for, and one that never finished is
# completed; when the package still cannot run, one line on stderr says why and
# what to do, and the exit status is 1. Every other exit status is the
# module's own. With --hook before the module, outside a git work tree it exits 0 and
# prints nothing.

# A hook passes --hook first: outside a git work tree it then does nothing and exits 0
# silently, where a skill's call exits 78 (basstler.exit_codes.ShellConfigurationExitCode).
# Read by resolve-personal-notes-config.sh, which this sources.
OUTSIDE_REPOSITORY_IS_NO_OP=false
if [ "${1:-}" = "--hook" ]; then
  OUTSIDE_REPOSITORY_IS_NO_OP=true
  shift
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/resolve-personal-notes-config.sh"

if [ "$#" -lt 1 ]; then
  echo "usage: basstler.sh <module> [arguments...]" >&2
  exit 2
fi

ready_basstler_python

MODULE="$1"
shift
exec "${BASSTLER_PYTHON}" -m "basstler.${MODULE}" "$@"
