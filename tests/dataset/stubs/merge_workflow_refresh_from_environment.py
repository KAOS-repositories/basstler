"""
Stands in for :mod:`basstler.plan_site.merge_workflow_refresh`'s command.

It prints the file ``STUB_MERGE_WORKFLOW_REFRESH_OUTPUT`` names, and with
``STUB_MERGE_WORKFLOW_REFRESH_FAILURE`` set it prints that to the error stream and
exits with status 1 instead. With neither set it prints nothing, as the command does for
a merge workflow that is current.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

failure = os.environ.get("STUB_MERGE_WORKFLOW_REFRESH_FAILURE")
output = os.environ.get("STUB_MERGE_WORKFLOW_REFRESH_OUTPUT")
if failure:
    print(failure, file=sys.stderr)
    sys.exit(1)
if output:
    print(Path(output).read_text(encoding="utf-8").rstrip("\n"))
