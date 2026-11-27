from __future__ import annotations

from package.storage import Reader, Store

ROWS = Reader({}).read(Store().rows)
