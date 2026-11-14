"""
Writes text in the locale encoding, its arguments ending in a comma.
"""

from __future__ import annotations

from pathlib import Path

Path("page.html").write_text(
    "→",
)
