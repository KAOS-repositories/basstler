from __future__ import annotations

from other_shapes import Shape as ImportedShape


def offset_corner(shape: ImportedShape, by: float) -> float:
    return shape.moved(by)
