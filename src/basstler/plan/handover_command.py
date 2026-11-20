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
from basstler.github.repository import RepositoryBranch
from basstler.github.repository_details import RepositoryDetailsRead
from basstler.github.repository_option import RepositoryArgument
from basstler.locations import PlanHandoverLocation
from basstler.plan.handover import PlanHandover
from basstler.plan.handover_continuation import HandoverImport
from basstler.plan.handover_options import PlanHandoverCommand, PlanHandoverOption
from basstler.plan.handover_originals import SenderOriginalPullRequests
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
    name=PlanHandoverCommand.GROUP,
    help="Hand plans over to another person, and take handed-over plans on.",
)
"""
The ``plan-handover`` command group.
"""


@plan_handover_app.command(name=PlanHandoverCommand.EXPORT)
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


@plan_handover_app.command(name=PlanHandoverCommand.OFFER)
def offer_plans(
    plans: list[str],
    *,
    receiver_repository: Annotated[
        RepositoryArgument, Parameter(name=PlanHandoverOption.RECEIVER_REPOSITORY)
    ],
    base: str | None = None,
    receiver_login: Annotated[
        str | None, Parameter(name=PlanHandoverOption.RECEIVER_LOGIN)
    ] = None,
    close_pull_requests: bool = False,
) -> PlanHandoverExitCode:
    """
    Offer plans of this repository's notes branch to another person as a draft pull
    request on their repository, carrying what ``export`` writes.

    :param plans: The ids of the plans to hand over, with every plan they depend on.
    :param receiver_repository: The receiver's repository as ``owner/name``: their
        fork, or this one if they push to it.
    :param base: The branch the pull request is opened against; the repository's
        default branch when not given.
    :param receiver_login: The receiver's GitHub login, mentioned in the pull request.
    :param close_pull_requests: Close the open pull requests of the plans' underway
        items on this repository, which the receiver continues on theirs.
    :raises PlanOutsideHandoverError: If a plan depends on a plan not named.
    """
    project_root = Path.cwd()
    client = GitHubRestClient()
    git = GitCommandRunner(project_root)
    if base is None:
        details = RepositoryDetailsRead(receiver_repository)
        base = details.parse(client.get(details.path)).default_branch.name
    handover = PlanHandover.from_notes_branch(
        project_root=project_root, plan_identifiers=plans
    )
    offered = HandoverOffer(
        handover=handover,
        base=RepositoryBranch(repository=receiver_repository, name=base),
        receiver_login=receiver_login,
        git=git,
    ).push_and_open_pull_request(client=client)
    logger.info(f"Offered the plans in {offered.url}.")
    if not close_pull_requests:
        return PlanHandoverExitCode.SUCCESS
    closed = SenderOriginalPullRequests(
        handover=handover,
        receiver_repository=receiver_repository,
        git=git,
        client=client,
    ).close_open_originals(handover_pull_request=offered)
    for original in closed:
        logger.info(f"Closed {original.url}.")
    return PlanHandoverExitCode.SUCCESS


@plan_handover_app.command(name=PlanHandoverCommand.DELETE_BRANCHES)
def delete_branches(
    plans: list[str],
    *,
    receiver_repository: Annotated[
        RepositoryArgument, Parameter(name=PlanHandoverOption.RECEIVER_REPOSITORY)
    ],
) -> PlanHandoverExitCode:
    """
    Delete this repository's branches of handed-over plans' unmerged pull requests once
    the receiver's repository holds each one's work, closing any still open. Pull
    requests themselves cannot be deleted on GitHub; closed, they stay listed.

    :param plans: The ids of the plans handed over, as offered.
    :param receiver_repository: The receiver's repository as ``owner/name``, as
        offered.
    :raises PlanOutsideHandoverError: If a plan depends on a plan not named.
    """
    project_root = Path.cwd()
    deletions = SenderOriginalPullRequests(
        handover=PlanHandover.from_notes_branch(
            project_root=project_root, plan_identifiers=plans
        ),
        receiver_repository=receiver_repository,
        git=GitCommandRunner(project_root),
        client=GitHubRestClient(),
    ).delete_continued_branches()
    for original in deletions.deleted:
        logger.info(f"Deleted {original.summary.head.name} of {original.url}.")
    for original in deletions.kept:
        logger.info(
            f"Kept {original.summary.head.name} of {original.url}: "
            f"{receiver_repository.full_name} does not hold its commit on a branch of "
            "that name."
        )
    return PlanHandoverExitCode.SUCCESS


@plan_handover_app.command(name=PlanHandoverCommand.REMOVE)
def remove_plans(plans: list[str]) -> PlanHandoverExitCode:
    """
    Remove handed-over plans, and their items' progress notes, from this repository's
    notes branch.

    :param plans: The ids of the plans handed over, as offered.
    :raises PlanOutsideHandoverError: If a plan depends on a plan not named.
    :raises PlanStillNamedError: If a plan staying on the notes branch depends on one
        of them.
    """
    project_root = Path.cwd()
    handover = PlanHandover.from_notes_branch(
        project_root=project_root, plan_identifiers=plans
    )
    handover.remove_from_notes_branch(project_root=project_root)
    logger.info(
        f"Removed plans {', '.join(plan.identifier for plan in handover.plans)} and "
        f"{len(handover.progress_notes)} progress notes from the notes branch."
    )
    return PlanHandoverExitCode.SUCCESS


import_source = Group("Source", validator=MutuallyExclusive())
"""
Where an import reads the handover from: a directory, one pull request or every one, at
most one of them.
"""


@plan_handover_app.command(name=PlanHandoverCommand.IMPORT)
def import_plans(
    directory: Annotated[
        ExistingDirectory | None, Parameter(group=import_source)
    ] = None,
    *,
    pull_request: Annotated[
        int | None,
        Parameter(name=PlanHandoverOption.PULL_REQUEST, group=import_source),
    ] = None,
    every_pull_request: Annotated[
        bool, Parameter(name=PlanHandoverOption.ALL, negative=(), group=import_source)
    ] = False,
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
    :param every_pull_request: Take over every handover pull request open here, oldest
        first.
    :param leave_underway_work: Leave underway items naming their pull requests on the
        other repository instead of continuing them here.
    :raises HandoverPullRequestNotChosenError: If no handover pull request is open, the
        one named is not, or several are and neither one nor all was asked for.
    :raises PlanAlreadyTrackedError: If the notes branch already holds one of its plans.
    """
    importing = HandoverImport(
        project_root=Path.cwd(),
        client=GitHubRestClient(),
        continues_underway_work=not leave_underway_work,
    )
    if directory is not None:
        taken_over = [importing.save(PlanHandover.from_directory(directory))]
    else:
        taken_over = HandoverPullRequests(
            git=GitCommandRunner(importing.project_root)
        ).import_and_close(
            importing=importing,
            requested_number=pull_request,
            takes_every_one=every_pull_request,
        )
    for continued in taken_over:
        for continuation in continued.continuations:
            logger.info(
                f"{continuation.original.item.text} continues in "
                f"{continuation.continued.url}."
            )
        logger.info(
            "Took over plans "
            f"{', '.join(plan.identifier for plan in continued.handover.plans_in_saving_order)} "
            f"and {len(continued.handover.progress_notes)} progress notes."
        )
    return PlanHandoverExitCode.SUCCESS
