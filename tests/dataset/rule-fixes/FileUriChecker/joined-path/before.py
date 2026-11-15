"""
Builds a file URL by putting a path joined in place after ``file://``.
"""

from __future__ import annotations

from pathlib import Path

root = Path("root").resolve()
page = "page.html"
url = f"file://{root / page}"
