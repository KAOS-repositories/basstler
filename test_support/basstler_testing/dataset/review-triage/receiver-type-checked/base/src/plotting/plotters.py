"""
Two plotters whose ``plot`` methods take different parameters, and a factory whose
return type only a type checker infers.
"""

from __future__ import annotations


class TrajectoryPlotter:
    def plot(self, file_name: str) -> None:
        print(file_name)


class GoalPlotter:
    def plot(self, goal_id: int) -> None:
        print(goal_id)


def trajectory_plotter():
    return TrajectoryPlotter()


def annotated_trajectory_plotter() -> TrajectoryPlotter:
    return TrajectoryPlotter()
