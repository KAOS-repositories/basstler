#!/usr/bin/env bash
# Prints the path given as the first argument as this platform's bash writes it.
if command -v cygpath >/dev/null; then
    cygpath --unix "$1"
else
    printf '%s\n' "$1"
fi
