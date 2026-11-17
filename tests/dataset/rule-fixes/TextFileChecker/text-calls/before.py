"""
Reads and writes text through the methods of a path.
"""

from __future__ import annotations

from pathlib import Path

page = Path("page.html")
page.write_text("→", encoding="utf-8")
text = page.read_text(encoding="utf-8")
page.with_suffix(".txt").write_text(text)
