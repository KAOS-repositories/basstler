"""
The ``basstler plan-handover`` commands: handing plans over to another person and taking
them over.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from cyclopts import App, Group, Parameter
from cyclopts.types import ExistingDirectory
from cyclopts.validators import MutuallyExclusive

from basstler.exit_codes import ExitCode
from basstler.git.commands import GitCommandRunner
from basstler.github.client import GitHubRestClient
from basstler.github.repository import Repository, RepositoryBranch
from basstler.github.repository_details import RepositoryDetailsRead
from basstler.locations import PlanHandoverLocation
from basstler.plan.handover import PlanHandover
from basstler.plan.handover_continuation import HandoverImport
from basstler.plan.handover_pull_request import HandoverOffer, HandoverPullRequests
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


@plan_handover_app.command(name="offer")
def offer_plans(
    plans: list[str],
    *,
    to: str,
    base: str | None = None,
    receiver: str | None = None,
) -> PlanHandoverExitCode:
    """
    Offer plans of this repository's notes branch to another person as a draft pull
    request on their repository, carrying what ``export`` writes.

    :param plans: The ids of the plans to hand over, with every plan they depend on.
    :param to: The receiver's repository as ``owner/name``: their fork, or this one if
        they push to it.
    :param base: The branch the pull request is opened against; the repository's
        default branch when not given.
    :param receiver: The receiver's GitHub login, mentioned in the pull request.
    :raises PlanOutsideHandoverError: If a plan depends on a plan not named.
    """
    project_root = Path.cwd()
    client = GitHubRestClient()
    target = Repository.parse(to)
    if base is None:
        details = RepositoryDetailsRead(target)
        base = details.parse(client.get(details.path)).default_branch.name
    offered = HandoverOffer(
        handover=PlanHandover.from_notes_branch(
            project_root=project_root, plan_identifiers=plans
        ),
        base=RepositoryBranch(repository=target, name=base),
        receiver=receiver,
        git=GitCommandRunner(project_root),
    ).offer(client=client)
    logger.info(f"Offered the plans in {offered.url}.")
    return PlanHandoverExitCode.SUCCESS


import_source = Group("Source", validator=MutuallyExclusive())
"""
Where an import reads the handover from: a directory or a pull request, at most one.
"""


@plan_handover_app.command(name="import")
def import_plans(
    directory: Annotated[
        ExistingDirectory | None, Parameter(group=import_source)
    ] = None,
    *,
    pull_request: Annotated[int | None, Parameter(group=import_source)] = None,
    leave_underway_work: bool = False,
) -> PlanHandoverExitCode:
    """
    Save a handover onto this repository's notes branch, from the handover pull
    request open here, which is then closed, or from an exported directory. Plans on
    another repository move here, and their items with open pull requests continue in
    pull requests opened here.

    :param directory: A handover directory to read instead of a pull request.
    :param pull_request: The number of the handover pull request to take over, when
        several are open.
    :param leave_underway_work: Leave underway items naming their pull requests on the
        other repository instead of continuing them here.
    :raises HandoverPullRequestNotChosenError: If no single open handover pull request
        matches.
    :raises PlanAlreadyTrackedError: If the notes branch already holds one of its plans.
    """
    importing = HandoverImport(
        project_root=Path.cwd(),
        client=GitHubRestClient(),
        continues_underway_work=not leave_underway_work,
    )
    if directory is not None:
        continued = importing.save(PlanHandover.from_directory(directory))
    else:
        continued = HandoverPullRequests(
            git=GitCommandRunner(importing.project_root)
        ).take_over(importing=importing, requested_number=pull_request)
    for continuation in continued.continuations:
        logger.info(
            f"{continuation.plan_identifier}/{continuation.item_identifier} continues "
            f"in {continuation.continued.url}."
        )
    logger.info(
        "Took over plans "
        f"{', '.join(plan.identifier for plan in continued.handover.plans_in_saving_order)} "
        f"and {len(continued.handover.progress_notes)} progress notes."
    )
    return PlanHandoverExitCode.SUCCESS
