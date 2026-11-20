"""
A subclass whose bases span several lines.
"""

from __future__ import annotations

import shape


class Square(  # a comment that closes its own (parenthesis)
    shape.Shape,
):
    """
    Inherits from :class:`Shape` on a line after the one that defines it.
    """
