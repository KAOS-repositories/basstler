"""
Builds file URLs by putting a path after ``file://``.
"""

from __future__ import annotations

from pathlib import Path

repository = Path("repository").resolve()
url = f"file://{repository}"
nested_url = str(f"file://{repository.parent}")
