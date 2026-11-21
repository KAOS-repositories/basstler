from __future__ import annotations


class TrajectoryPlotter:
    def plot(self, file_name: str) -> TrajectoryPlotter:
        print(file_name)
        return self


class GoalPlotter:
    def plot(self, goal_id: int) -> None:
        print(goal_id)


def plot_each(points: list[str]) -> None:
    for point in points:
        plotter = TrajectoryPlotter()
        if point:
            plotter.title = point
        plotter = plotter.plot(file_name=point)
        plotter.plot(file_name=point)
        plotter = GoalPlotter()
        plotter.plot(goal_id=len(point))
