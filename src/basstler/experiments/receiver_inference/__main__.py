"""
Run the receiver inference experiment::

    python -m basstler.experiments.receiver_inference owner/name#123 \\
        owner/name#456:module-documentation --checkout path/to/clone
"""

from __future__ import annotations

from pathlib import Path

from cyclopts import App

from basstler.experiments.receiver_inference.experiment import (
    PullRequestCase,
    ReceiverInferenceExperiment,
)
from basstler.experiments.receiver_inference.type_checkers import (
    Mypy,
    Pyrefly,
    Pyright,
    TypeChecker,
)
from basstler.experiments.tool_installation import ToolInstallation
from basstler.locations import ExperimentLocation

EXPERIMENT_NAME = "receiver-inference"
"""
The name the experiment's command and result files share.
"""

TYPE_CHECKERS: tuple[TypeChecker, ...] = (
    Mypy(ToolInstallation("mypy", ExperimentLocation.TOOLS / "mypy")),
    Pyright(
        ToolInstallation(
            "pyright",
            ExperimentLocation.TOOLS / "pyright",
            extras=("nodejs",),
            downloads=(ExperimentLocation.TOOLS / "pyright" / "downloads",),
        )
    ),
    Pyrefly(ToolInstallation("pyrefly", ExperimentLocation.TOOLS / "pyrefly")),
)
"""
The latest release of each type checker compared, with the Node.js pyright runs on.
"""

app = App(
    name=EXPERIMENT_NAME,
    help="Compare basstler's receiver inference with type checkers on pull requests.",
)
"""
The experiment's command.
"""


@app.default
def run(
    *pull_requests: str,
    checkout: Path,
    repetitions: int = 2,
    output: Path = ExperimentLocation.RESULTS,
) -> None:
    """
    Triage each pull request once per way of inferring receivers, and write the tables.

    :param pull_requests: Each as ``owner/name#number``, optionally followed by
        ``:rule,rule`` naming opt-in triage rules.
    :param checkout: A clone holding the pull requests' commits.
    :param repetitions: How often each triage is timed.
    :param output: The directory the tables are written to.
    """
    experiment = ReceiverInferenceExperiment(
        checkout,
        tuple(map(PullRequestCase.parse, pull_requests)),
        TYPE_CHECKERS,
        repetitions,
    )
    outcomes, costs = experiment.run()
    for table, name in (
        (outcomes, EXPERIMENT_NAME),
        (costs, f"{EXPERIMENT_NAME}-costs"),
    ):
        written, _ = table.write(output, name)
        print(written)
        print(table.markdown())


if __name__ == "__main__":
    app()
