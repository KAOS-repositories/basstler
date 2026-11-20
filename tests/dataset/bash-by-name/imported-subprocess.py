"""
Runs bash by its name through :mod:`subprocess` imported under other names.
"""

from __future__ import annotations

import subprocess as processes
from subprocess import run

processes.run(["bash", "-c", "true"], check=True)
run(["bash", "-c", "true"], check=True)
