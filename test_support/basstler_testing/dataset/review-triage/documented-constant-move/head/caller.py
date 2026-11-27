from __future__ import annotations

from package.limits import ROW_LIMIT
from package.storage import Store

ROWS = Store().rows[:ROW_LIMIT]
