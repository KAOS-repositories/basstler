from __future__ import annotations


class Rotation:
    def dot(self, other: Rotation) -> Rotation:
        return other


class ProbabilityTable:
    def dot(self, values: list[float]) -> float:
        return sum(values)


class ConstraintBuilder:
    @staticmethod
    def turned_each(*, current: Rotation, tables: list[ProbabilityTable]) -> None:
        for table in tables:
            current.dot(table)
            current = table
