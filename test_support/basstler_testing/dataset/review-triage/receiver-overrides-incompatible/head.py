from __future__ import annotations


class Plotter:
    def plot(self, file_name: str) -> None:
        print(file_name)


class TrajectoryPlotter(Plotter):
    def plot(self, file_name: str) -> None:
        print(file_name.upper())


class GoalPlotter(Plotter):
    def plot(self, goal_id: str) -> None:
        print(goal_id)


def draw(plotter: Plotter) -> None:
    plotter.plot(file_name="trajectory.pdf")
