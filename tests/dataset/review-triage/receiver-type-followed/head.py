from __future__ import annotations

from dataclasses import dataclass, field


class TrajectoryPlotter:
    def plot(self, file_name: str) -> None:
        print(file_name)


class GoalPlotter:
    def plot(self, goal_id: int) -> None:
        print(goal_id)


@dataclass
class Recorded:
    name: str

    def follow(self, expression: str) -> None:
        print(expression)


class Follower:
    def follow(self, leader: str) -> None:
        print(leader)


@dataclass
class Trajectory:
    recorded: list[Recorded] = field(default_factory=list)
    plotters: dict[int, TrajectoryPlotter] = field(default_factory=dict)

    @classmethod
    def from_names(cls, names: list[str]) -> Trajectory:
        return cls([Recorded(name) for name in names])

    def follow(self, expressions: list[str]) -> None:
        pending = list(self.recorded)
        for expression in expressions:
            recorded = next(
                (recorded for recorded in pending if recorded.name == expression),
                None,
            )
            if recorded is None:
                continue
            pending.remove(recorded)
            recorded.follow(expression=expression)
        for recorded in pending:
            recorded.follow(expression="stopped")

    def plot_all(self) -> None:
        for plotter in self.plotters.values():
            plotter.plot(file_name="all.pdf")
        self.plotters.pop(0).plot(file_name="first.pdf")
        last = sorted(self.plotters)[-1]
        self.plotters[last].plot(file_name="last.pdf")


trajectory = Trajectory.from_names(["a", "b"])
for recorded in trajectory.recorded[1:]:
    recorded.follow(expression="again")


def make_plotter() -> TrajectoryPlotter:
    return TrajectoryPlotter()


make_plotter().plot(file_name="made.pdf")
