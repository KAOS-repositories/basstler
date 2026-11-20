"""
Reads and writes text through the methods of a path.
"""

from __future__ import annotations

from pathlib import Path
from basstler.text_file import TextFile

page = Path("page.html")
TextFile(page).write("→")
text = TextFile(page).read()
TextFile(page.with_suffix(".txt")).write(text)
