"""
Imports of one name from the module it moves out of, and of others from the same one.
"""

from __future__ import annotations

from typing import Any

from helpers import Other
from relocated import Mover
from relocated import Mover as Alias
from elsewhere import Mover as Untouched

value: Any = (Mover, Alias, Other, Untouched)
