from __future__ import annotations


class Rotation:
    def dot(self, other: Rotation) -> Rotation:
        return other


class ProbabilityTable:
    def dot(self, values: list[float]) -> float:
        return sum(values)


class ConstraintBuilder:
    @staticmethod
    def turned(*, current: Rotation, offset: Rotation) -> Rotation:
        current = current.dot(other=offset)
        return current
