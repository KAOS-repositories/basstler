#!/bin/bash
set -uo pipefail

# Stands in for uv in review-triage.sh's tests, so they install nothing. Records each
# argument on a line of its own; a sync also puts an interpreter into the project
# environment, as a real one does.
#   STUB_UV_CALL_LOG - file the arguments are appended to
#   STUB_UV_PYTHON   - the interpreter a sync puts into UV_PROJECT_ENVIRONMENT

printf '%s\n' "$@" >> "${STUB_UV_CALL_LOG}"
if [[ "${1:-}" == sync ]]; then
    mkdir -p "${UV_PROJECT_ENVIRONMENT}/bin"
    cp "${STUB_UV_PYTHON}" "${UV_PROJECT_ENVIRONMENT}/bin/python"
fi
