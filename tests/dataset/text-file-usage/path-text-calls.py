"""
Reads and writes text through the methods of a path, as UTF-8 or in the locale encoding.
"""

from __future__ import annotations

from pathlib import Path

page = Path("page.html")
page.read_text()
page.read_text(encoding="utf-8")
page.write_text("→")
page.write_text("→", encoding="utf-8")
