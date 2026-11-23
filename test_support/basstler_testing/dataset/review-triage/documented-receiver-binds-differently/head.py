"""
Plotting goals.
"""

from __future__ import annotations


class GoalPlotter:
    def plot(self, goal_id: int) -> None:
        print(goal_id)


def make_plotter() -> GoalPlotter:
    return GoalPlotter()


plotter = make_plotter()
plotter.plot(file_name=3)
