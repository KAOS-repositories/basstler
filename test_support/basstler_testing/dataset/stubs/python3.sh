#!/bin/sh
# Stands in for python3 where the suite's environment names its interpreter only
# python, as a Windows virtual environment does; that python is first on PATH.
exec python "$@"
