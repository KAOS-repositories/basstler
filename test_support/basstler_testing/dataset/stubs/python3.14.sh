#!/bin/sh
# Stands in for a supported interpreter found by name: answers the query for its
# own path, and runs `-m pip` through the pip stub on PATH.
if [ "${1:-}" = "-c" ]; then
  printf '%s\n' "$0"
  exit 0
fi
if [ "${1:-}" = "-m" ] && [ "${2:-}" = "pip" ]; then
  shift 2
  exec pip "$@"
fi
echo "python stub: unrecognized invocation: $*" >&2
exit 64
