#!/bin/bash
set -uo pipefail

# Test stub standing in for `uv`, so session-start.sh's tests can exercise the
# environment it creates without fetching or creating a real interpreter.
# Copied into place as an executable named `uv`, earlier on PATH than any real
# one; see the stub_bin fixture in conftest.py.
#
# Recognizes only the two invocations the hooks make:
#   `venv --no-project --python <requirement> <directory>`, from
#     create_basstler_environment, which it answers by writing
#     <directory>/<STUB_UV_ENVIRONMENT_INTERPRETER> as a script running
#     STUB_UV_PYTHON - the interpreter running the suite;
#   `sync --frozen --package basstler --no-dev --project <workspace>
#     [--no-editable]`, from install_basstler_into_environment, which installs
#     nothing.
#   STUB_UV_CALL_LOG - file the invocation is appended to
#   STUB_UV_STATUS   - exit status to report, default 0; anything else creates
#                      and installs nothing
#   STUB_UV_ENVIRONMENT_INTERPRETER - where in the environment the interpreter
#                      is written, default bin/python; Scripts/python.exe stands
#                      in for Windows
#   STUB_UV_WATCHED_FILE - a file whose content, as it is while the stub runs,
#                      is copied to STUB_UV_WATCHED_FILE_COPY
#
# Exits 64 on an unrecognized invocation for the same reason gh.sh does: a
# changed call must fail a test rather than pass by accident.

if [ -n "${STUB_UV_CALL_LOG:-}" ]; then
  printf '%s\n' "$*" >> "${STUB_UV_CALL_LOG}"
fi

if [ -n "${STUB_UV_WATCHED_FILE:-}" ]; then
  cat "${STUB_UV_WATCHED_FILE}" > "${STUB_UV_WATCHED_FILE_COPY}" 2>/dev/null
fi

STATUS="${STUB_UV_STATUS:-0}"

if [ "${1:-}" = "sync" ] && [ "${2:-}" = "--frozen" ] && [ "${3:-}" = "--package" ] \
    && [ "${4:-}" = "basstler" ] && [ "${5:-}" = "--no-dev" ] \
    && [ "${6:-}" = "--project" ] && [ -n "${7:-}" ]; then
  if [ "${STATUS}" != "0" ]; then
    echo "error: stub uv refused to install $7" >&2
    exit "${STATUS}"
  fi
  echo "Installed $7"
  exit 0
fi

if [ "${1:-}" != "venv" ] || [ "${2:-}" != "--no-project" ] \
    || [ "${3:-}" != "--python" ] || [ -z "${4:-}" ] || [ -z "${5:-}" ]; then
  echo "uv stub: unrecognized invocation: $*" >&2
  exit 64
fi

if [ "${STATUS}" != "0" ]; then
  echo "error: stub uv found no interpreter satisfying $4" >&2
  exit "${STATUS}"
fi

INTERPRETER="$5/${STUB_UV_ENVIRONMENT_INTERPRETER:-bin/python}"
mkdir -p "$(dirname "${INTERPRETER}")"
printf '#!/bin/sh\nexec "%s" "$@"\n' "${STUB_UV_PYTHON}" > "${INTERPRETER}"
chmod +x "${INTERPRETER}"
echo "Creating virtual environment at: $5"
