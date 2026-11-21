"""
Calls a function, and never spells the name of the one that removes directories.
"""

from __future__ import annotations

import shutil

shutil.copytree("clone", "copy")
