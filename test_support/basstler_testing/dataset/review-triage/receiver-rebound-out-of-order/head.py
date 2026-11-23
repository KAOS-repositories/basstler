from __future__ import annotations


class TrajectoryPlotter:
    def plot(self, file_name: str) -> None:
        print(file_name)


class GoalPlotter:
    def plot(self, goal_id: int) -> None:
        print(goal_id)


def rebound_by_the_next_iteration(points: list[str]) -> None:
    plotter = TrajectoryPlotter()
    for point in points:
        plotter.plot(file_name=point)
        plotter = GoalPlotter()


def rebound_by_a_closure(point: str) -> None:
    def switch() -> None:
        nonlocal plotter
        plotter = GoalPlotter()

    plotter = TrajectoryPlotter()
    switch()
    plotter.plot(file_name=point)


def rebound_before_an_else_clause(point: str) -> None:
    plotter = TrajectoryPlotter()
    try:
        plotter = GoalPlotter()
    except ValueError:
        pass
    else:
        plotter.plot(file_name=point)


def rebound_by_a_condition(point: str) -> None:
    plotter = TrajectoryPlotter()
    if (plotter := GoalPlotter()) and point:
        plotter.plot(file_name=point)
