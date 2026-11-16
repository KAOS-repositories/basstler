from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeVar


class TrajectoryPlotter:
    def plot(self, file_name: str) -> None:
        print(file_name)


class GoalPlotter:
    def plot(self, goal_id: int) -> None:
        print(goal_id)


class Extension:
    pass


@dataclass
class Recording(Extension):
    plotter: TrajectoryPlotter = field(default_factory=TrajectoryPlotter)


GenericExtension = TypeVar("GenericExtension", bound=Extension)


class Executor:
    def __init__(self, extensions: list[Extension]) -> None:
        self.extensions = extensions

    def require_extension(
        self, extension_type: type[GenericExtension]
    ) -> GenericExtension:
        return next(e for e in self.extensions if type(e) is extension_type)


def goal_plotter() -> GoalPlotter:
    return GoalPlotter()


executor = Executor([Recording()])
executor.require_extension(extension_type=Recording).plotter.plot(
    file_name="trajectory.pdf"
)
goal_plotter().plot(goal_id=3)


def plot_with(recording: Recording) -> None:
    plotter = recording.plotter
    plotter.plot(file_name="recording.pdf")
