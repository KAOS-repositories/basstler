"""
Copies text in the locale encoding, reading it inside the call writing it.
"""

from __future__ import annotations

from pathlib import Path

source = Path("source.txt")
Path("copy.txt").write_text(source.read_text())
