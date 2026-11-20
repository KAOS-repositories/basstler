#!/bin/bash
set -uo pipefail

# Stands in for the interpreter of review-triage.sh's environment, so its tests run
# without installing basstler. Runs nothing; records each argument on a line of its own.
#   STUB_PYTHON_CALL_LOG - file the arguments are appended to

printf '%s\n' "$@" >> "${STUB_PYTHON_CALL_LOG}"
