from __future__ import annotations


class TrajectoryPlotter:
    def plot(self, file_name: str) -> None:
        print(file_name)


class GoalPlotter:
    def plot(self, goal_id: int) -> None:
        print(goal_id)


def plot_all(plotters):
    for plotter in plotters:
        plotter.plot(file_name="trajectory.pdf")
