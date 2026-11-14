"""
Reads and writes text in the locale encoding.
"""

from __future__ import annotations

from pathlib import Path

page = Path("page.html")
page.write_text("→", encoding="utf-8")
page.read_text(encoding="utf-8")
open(page, encoding="utf-8")
page.open("w", encoding="utf-8")
