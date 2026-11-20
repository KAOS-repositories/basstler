from __future__ import annotations


class TrajectoryPlotter:
    def plot(self, file_name: str) -> None:
        print(file_name)


class GoalPlotter:
    def plot(self, goal_id: int) -> None:
        print(goal_id)


plotter = TrajectoryPlotter()


def rebound(first: bool) -> None:
    plotter = TrajectoryPlotter()
    if first:
        plotter = GoalPlotter()
    plotter.plot(1)


def shadowed_by_lambda(plotters) -> None:
    for draw in map(lambda plotter: plotter.plot(2), plotters):
        print(draw)


def shadowed_by_comprehension(plotters) -> None:
    print([plotter.plot(3) for plotter in plotters])


def captured(value: object) -> None:
    plotter = TrajectoryPlotter()
    match value:
        case GoalPlotter() as plotter:
            pass
    plotter.plot(4)
