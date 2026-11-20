"""
Calls without arguments, with one argument, and with a trailing comma.
"""

from __future__ import annotations


def run(command=None, check=False):
    return command, check


command = "ls"
run(check=True)
run(command, check=True)
run(
    command,
    check=True,
)
