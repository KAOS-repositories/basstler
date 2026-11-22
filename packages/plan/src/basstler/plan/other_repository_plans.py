"""
The plans of another repository's notes, read so a goal can name items kept there.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from basstler.git.commands import GitCommandRunner
from basstler.github.repository import GitHubAddress, Repository
from basstler.locations import ProjectLocation
from basstler.plan.dependencies import PlanDirectory
from basstler.plan.model import PlanDocument
from basstler.standard_streams import StandardStreamHandler
from basstler.text_file import TextFile

logger = StandardStreamHandler.logger_for(__name__)
"""
This module's logger, which says why a repository's plans could not be read.
"""

FETCHED_NOTES = "FETCH_HEAD"
"""
The ref a fetched notes branch is read from in the scratch repository.
"""


@dataclass(frozen=True)
class OtherRepositoryPlans:
    """
    Fetches another repository's notes branch into a scratch directory and writes its
    plans' manifests out, as :meth:`PlanDirectory.resolve` reads them.
    """

    scratch: Path
    """
    A directory of its own to fetch into, one subdirectory a repository.
    """

    notes_branch: str
    """
    The branch the other repositories keep their notes on.
    """

    remote_root: str = GitHubAddress.WEB.value
    """
    Where repositories are fetched from, as :meth:`Repository.clone_url_under` takes it.
    """

    def read(self, repository: str) -> PlanDirectory | None:
        """
        :param repository: The repository whose notes hold the plans, as ``owner/name``.
        :return: Its plans, or ``None`` when its notes branch cannot be fetched.
        """
        parsed = Repository.parse(repository)
        destination = self.scratch / f"{parsed.owner}--{parsed.name}"
        checkout = destination / "repository"
        checkout.mkdir(parents=True)
        git = GitCommandRunner(checkout)
        git.run("init", "--quiet")
        fetched = git.attempt(
            "fetch",
            "--quiet",
            "--depth=1",
            parsed.clone_url_under(self.remote_root),
            self.notes_branch,
        )
        if not fetched.succeeded:
            logger.warning(
                f"{repository}: cannot fetch {self.notes_branch}: "
                f"{fetched.error_output}; its plans are left out"
            )
            return None
        plans = destination / "plans"
        listing = git.run(
            "ls-tree",
            "-r",
            "--name-only",
            FETCHED_NOTES,
            PurePosixPath(ProjectLocation.PLANS).as_posix(),
        )
        for name in listing.splitlines():
            path = PurePosixPath(name)
            if (
                path.name != PlanDocument.MANIFEST
                or path.parent.parent != PurePosixPath(ProjectLocation.PLANS)
            ):
                continue
            manifest = plans / path.parent.name / PlanDocument.MANIFEST
            manifest.parent.mkdir(parents=True)
            TextFile(manifest).write(git.run("show", f"{FETCHED_NOTES}:{path}") + "\n")
        plans.mkdir(exist_ok=True)
        return PlanDirectory(plans, repository=repository)

    def reading(self, plan_directory: PlanDirectory) -> PlanDirectory:
        """
        :param plan_directory: The plans of the notes a goal is read from.
        :return: The same plans, reading another repository's the first time a reference
            names it.
        """
        plan_directory.read_other_repository = self.read
        return plan_directory
