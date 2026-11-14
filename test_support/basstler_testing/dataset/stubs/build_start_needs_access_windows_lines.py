"""
Stands in for :mod:`basstler.plan_site.build_start` on Windows, printing that the session
cannot start the build yet over two lines that end as Windows ends them.
"""

from __future__ import annotations

import sys

sys.stdout.buffer.write(
    b"A plan save cannot start the build in an-owner/the-site yet.\r\nAttach it.\r\n"
)
