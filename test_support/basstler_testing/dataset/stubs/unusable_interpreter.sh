#!/bin/sh
# Stands in for an interpreter that is on PATH but cannot run, as a shim whose Python
# was uninstalled does.
echo "No suitable Python runtime found" >&2
exit 103
