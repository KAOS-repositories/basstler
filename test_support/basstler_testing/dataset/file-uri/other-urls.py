"""
Builds URLs that are not one path after ``file://``.
"""

from __future__ import annotations

from pathlib import Path

repository = Path("repository").resolve()
host = "example.com"
uri = repository.as_uri()
web_url = f"https://{host}"
page_url = f"file://{repository}/page.html"
converted_url = f"file://{repository!s}"
scheme = "file://"
labelled_url = (
    "the location of the repository this snippet names, which a clone is made from: "
    f"file://{repository}"
)
