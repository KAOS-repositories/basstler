"""
Clones a repository from a file URL built by putting its path after ``file://``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

remote = Path("remote").resolve()
subprocess.run(["git", "clone", "--quiet", remote.as_uri(), "clone"], check=True)
