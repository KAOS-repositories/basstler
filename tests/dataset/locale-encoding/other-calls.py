"""
Calls that are not of :func:`open`, though they are given what an opened file is given.
"""

from __future__ import annotations

fetch = print
page = None

fetch("page.html", "rb")
page.fetch("rb")
