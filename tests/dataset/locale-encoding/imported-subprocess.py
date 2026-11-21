"""
Decodes output in the locale encoding through :mod:`subprocess` imported under other
names.
"""

from __future__ import annotations

import subprocess as processes
from subprocess import run

processes.run(["git", "log"], text=True)  # violation
run(["git", "log"], text=True)  # violation
