"""
Reads and writes text in the locale encoding, which on Windows cannot encode most of
Unicode.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

page = Path("page.html")
page.write_text("→")  # violation
page.read_text()  # violation
open(page)  # violation
page.open("w")  # violation
subprocess.run(["git", "log"], text=True)  # violation
