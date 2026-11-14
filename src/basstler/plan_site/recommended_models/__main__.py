"""
Give every item of every plan on the notes branch the recommended model it lacks, and
push the result.

Usage:
    "${BASSTLER_PYTHON}" -m basstler.plan_site.recommended_models every-plan [--project-root DIRECTORY]
"""

from __future__ import annotations

from pathlib import Path

from cyclopts import App
from cyclopts.types import ExistingDirectory

from basstler.plan_site.recommended_models.every_plan import (
    RecommendedModelsCommand,
    RecommendedModelsInEveryPlan,
)
from basstler.standard_streams import StandardStreamHandler

logger = StandardStreamHandler.logger_for(__name__)
"""
This module's logger, which is also what its command prints through.
"""

# %% the command line


app = App(help=__doc__)
"""
The command.
"""


@app.command(name=RecommendedModelsCommand.EVERY_PLAN.value)
def fill_recommended_models_in_every_plan(
    *, project_root: ExistingDirectory = Path(), push_attempts: int = 5
) -> None:
    """
    Fill every plan's missing recommended models on the clone's notes branch, push the
    result and print what was done.

    :param project_root: The clone whose settings say where the notes are.
    :param push_attempts: How many pushes to make before giving up on a branch that
        keeps moving.
    """
    logger.info(
        RecommendedModelsInEveryPlan().record_on_notes_branch(
            project_root, push_attempts=push_attempts
        )
    )


if __name__ == "__main__":
    app()
