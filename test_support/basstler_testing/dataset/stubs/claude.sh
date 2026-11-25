#!/bin/bash
set -uo pipefail

# Test stub standing in for Claude Code's command line, so a test can see the
# session an agentic loop starts without starting one. Copied into place as an
# executable named `claude`; prints each argument it was run with on a line of
# its own, which the loop appends to its log.

printf '%s\n' "$@"
