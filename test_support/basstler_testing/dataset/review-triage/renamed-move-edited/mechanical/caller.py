from __future__ import annotations

from package.reading import Reader
from package.storage import Store

ROWS = Reader({}).read(Store().rows)
