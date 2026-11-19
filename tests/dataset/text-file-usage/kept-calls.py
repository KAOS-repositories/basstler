"""
Reads and writes text in ways a text file does not: another encoding, error handling,
newline translation.
"""

from __future__ import annotations

from pathlib import Path

ENCODING = "latin-1"
ENCODINGS = {"encoding": "utf-8"}
page = Path("page.html")
page.read_text(encoding=ENCODING)
page.read_text(encoding="latin-1")
page.read_text(errors="replace", encoding="utf-8")
page.write_text("→", newline="", encoding="utf-8")
page.read_text(**ENCODINGS)
page.read_bytes()
