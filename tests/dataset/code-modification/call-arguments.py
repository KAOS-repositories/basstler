"""
Calls without arguments, with one argument, and with a trailing comma.
"""

from __future__ import annotations


def run(command=None, check=False):
    return command, check


command = "ls"
run()
run(command)
run(
    command,
)
