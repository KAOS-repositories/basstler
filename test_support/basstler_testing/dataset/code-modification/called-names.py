"""
Calls of a name, an attribute, a subscript and a call's result.
"""

from __future__ import annotations

from pathlib import Path


def factory():
    return list


path = Path("page.html")
open(path)
path.read_text()
dict[str, int]()
factory()()
