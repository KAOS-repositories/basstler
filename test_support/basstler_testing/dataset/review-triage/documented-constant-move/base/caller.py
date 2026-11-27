from __future__ import annotations

from package.storage import ROW_LIMIT, Store

ROWS = Store().rows[:ROW_LIMIT]
