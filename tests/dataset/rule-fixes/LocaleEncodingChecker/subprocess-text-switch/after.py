"""
Decodes a command's output in the locale encoding.
"""

from __future__ import annotations

import subprocess

subprocess.run(["git", "log"], encoding="utf-8", check=True)
