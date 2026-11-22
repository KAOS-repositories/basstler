"""
Reads and writes text in the locale encoding.
"""

from __future__ import annotations

from pathlib import Path

page = Path("page.html")
page.write_text("→")
page.read_text()
open(page)
page.open("w")
