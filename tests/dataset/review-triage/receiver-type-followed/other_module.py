from __future__ import annotations


class GoalPlotter:
    def plot(self, goal_id: int) -> None:
        print(goal_id)


def make_plotter():
    return GoalPlotter()
