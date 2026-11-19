"""
The ``basstler plan-handover`` commands: handing plans over to another person and taking
them over.
"""

from __future__ import annotations

from pathlib import Path

from cyclopts import App
from cyclopts.types import ExistingDirectory

from basstler.exit_codes import ExitCode
from basstler.locations import PlanHandoverLocation
from basstler.plan.handover import PlanHandover
from basstler.standard_streams import StandardStreamHandler

logger = StandardStreamHandler.logger_for(__name__)
"""
This module's logger, which is also what its commands print through.
"""


class PlanHandoverExitCode(ExitCode):
    """
    What a ``basstler plan-handover`` command's exit status tells its caller.
    """

    SUCCESS = 0
    """
    The command did what it was asked; a failure raises instead.
    """


plan_handover_app = App(
    name="plan-handover",
    help="Hand plans over to another person, and take handed-over plans on.",
)
"""
The ``plan-handover`` command group.
"""


@plan_handover_app.command(name="export")
def export_plans(plans: list[str], *, output: Path) -> PlanHandoverExitCode:
    """
    Write plans of this repository's notes branch, their items' progress notes and the
    repository's rules into a directory, with a guide to working every item.

    :param plans: The ids of the plans to hand over, with every plan they depend on.
    :param output: The directory to write, created if missing.
    :raises PlanOutsideHandoverError: If a plan depends on a plan not named.
    """
    handover = PlanHandover.from_notes_branch(
        project_root=Path.cwd(), plan_identifiers=plans
    )
    handover.write(output)
    logger.info(
        f"Handed over {len(handover.plans)} plans with "
        f"{sum(len(plan.manifest.items) for plan in handover.plans)} items and "
        f"{len(handover.progress_notes)} progress notes into {output}; start from "
        f"{output / PlanHandoverLocation.GUIDE}."
    )
    return PlanHandoverExitCode.SUCCESS


@plan_handover_app.command(name="import")
def import_plans(directory: ExistingDirectory) -> PlanHandoverExitCode:
    """
    Save a handover's plans, progress notes and rules onto this repository's notes
    branch.

    :param directory: A directory ``basstler plan-handover export`` wrote.
    :raises PlanAlreadyTrackedError: If the notes branch already holds one of its plans.
    """
    handover = PlanHandover.from_directory(directory)
    handover.save_to_notes_branch(project_root=Path.cwd())
    logger.info(
        "Took over plans "
        f"{', '.join(plan.identifier for plan in handover.plans_in_saving_order)} "
        f"and {len(handover.progress_notes)} progress notes."
    )
    return PlanHandoverExitCode.SUCCESS
