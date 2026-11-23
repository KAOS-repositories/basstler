"""
A work clone with bare repositories standing in for its fork and its upstream, so
nothing touches the network.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from basstler.git.commands import GitCommandRunner
from basstler.locations import ProjectLocation

from .constants.paths import DatasetLocation
from .constants.stack import RemoteName
from .scratch_repository import initialize_bare_repository
from basstler.text_file import TextFile

# %% the branch every stack targets


UPSTREAM_BASE = "main"
"""
The branch every stack in these tests ultimately targets.
"""

# %% a real fork checkout to execute against


@dataclass
class ForkCheckout:
    """
    A work clone plus the bare repositories standing in for its fork and its upstream.

    Bare repositories live at paths ending ``<owner>/<name>.git`` and are addressed as
    ``file://`` URLs, because a remote is matched by the repository its URL names and a
    plain local path deliberately names none.
    """

    project_root: Path
    """
    The clone the executor runs in.
    """

    fork_path: Path
    """
    The bare repository the fork remote points at.
    """

    upstream_path: Path
    """
    The bare repository the upstream remote points at.
    """

    @classmethod
    def create(cls, parent_directory: Path) -> ForkCheckout:
        """
        Build a checkout with both remotes wired up and ``main`` published to each.

        :param parent_directory: Where to put the clone and the bare repositories.
        :return: The new checkout.
        """
        project_root = parent_directory / "project"
        project_root.mkdir(parents=True)
        checkout = cls(
            project_root,
            cls._bare_repository(parent_directory / "a-fork-owner" / "a-fork.git"),
            cls._bare_repository(
                parent_directory / "an-upstream-owner" / "a-project.git"
            ),
        )
        checkout.run_git("init", "--quiet")
        checkout.run_git("symbolic-ref", "HEAD", f"refs/heads/{UPSTREAM_BASE}")
        checkout.run_git("config", "user.name", "Scratch Fork")
        checkout.run_git("config", "user.email", "scratch-fork@example.com")
        checkout.run_git(
            "remote", "add", RemoteName.ORIGIN, checkout.fork_path.as_uri()
        )
        checkout.run_git(
            "remote", "add", RemoteName.UPSTREAM, checkout.upstream_path.as_uri()
        )
        checkout.commit("a-file", "the first line\n")
        checkout.run_git("push", "--quiet", RemoteName.ORIGIN, UPSTREAM_BASE)
        checkout.run_git("push", "--quiet", RemoteName.UPSTREAM, UPSTREAM_BASE)
        checkout.run_git("fetch", "--quiet", RemoteName.ORIGIN)
        checkout.run_git("fetch", "--quiet", RemoteName.UPSTREAM)
        return checkout

    def name_the_upstream(self) -> None:
        """
        Write the project's stack settings naming its upstream, untracked, so checking
        out a branch these tests cut never deletes them.
        """
        destination = self.project_root / ProjectLocation.PROJECT_STACK_CONFIGURATION
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(DatasetLocation.SCRATCH_FORK_STACK_CONFIGURATION, destination)

    @staticmethod
    def _bare_repository(path: Path) -> Path:
        """
        :param path: Where to create the bare repository, parents included.
        :return: The same path.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        return initialize_bare_repository(path)

    def run_git(self, *arguments: str) -> str:
        """
        Run git in the clone, failing the test if it reports an error.

        :param arguments: The arguments to pass to git.
        :return: The command's stripped stdout.
        """
        result = subprocess.run(
            ["git", *arguments],
            cwd=self.project_root,
            capture_output=True,
            encoding="utf-8",
        )
        assert result.returncode == 0, result.stderr
        return result.stdout.strip()

    def commit(self, name: str, content: str) -> str:
        """
        Write a file and commit it on the checked-out branch.

        :param name: The file to write.
        :param content: What to write into it.
        :return: The new commit's hash.
        """
        TextFile(self.project_root / name).write(content)
        self.run_git("add", name)
        self.run_git("commit", "--quiet", "-m", f"write {name}")
        return self.run_git("rev-parse", "HEAD")

    def branch_from(self, name: str, start_point: str) -> str:
        """
        Create a branch with a commit of its own, and publish it to the fork.

        The commit is what makes the branch a stack node rather than another name for
        its start point: a branch containing nothing of its own is an ancestor of the
        upstream base, which the derived stack reads - correctly - as already landed.

        :param name: The branch to create.
        :param start_point: What to start it from.
        :return: The branch's published commit hash.
        """
        self.run_git("checkout", "--quiet", "-B", name, start_point)
        commit = self.commit(self.own_file(name), f"the work on {name}\n")
        self.run_git("push", "--quiet", RemoteName.ORIGIN, f"{name}:{name}")
        self.run_git("fetch", "--quiet", RemoteName.ORIGIN)
        return commit

    @staticmethod
    def own_file(branch: str) -> str:
        """
        :param branch: The branch whose own file is wanted.
        :return: The file :meth:`branch_from` writes to give that branch a commit of its
            own, which is also what a test rewrites to move it. It sits at the top of
            the checkout whatever slashes the branch name has.
        """
        return f"{branch.replace('/', '-')}-file"

    def commit_on(self, branch: str, name: str, content: str) -> str:
        """
        Add a commit to a branch and publish it to the fork.

        :param branch: The branch to commit on.
        :param name: The file to write.
        :param content: What to write into it.
        :return: The branch's new published commit hash.
        """
        self.run_git("checkout", "--quiet", branch)
        commit = self.commit(name, content)
        self.run_git("push", "--quiet", RemoteName.ORIGIN, f"{branch}:{branch}")
        self.run_git("fetch", "--quiet", RemoteName.ORIGIN)
        return commit

    def published_commit(self, remote: str, branch: str) -> str:
        """
        :param remote: The remote to read from.
        :param branch: The branch to read.
        :return: The commit that branch points at on that remote.
        """
        return self.run_git("rev-parse", f"{remote}/{branch}")

    def published_file(self, remote: str, branch: str, name: str) -> str:
        """
        :param remote: The remote to read from.
        :param branch: The branch to read.
        :param name: The file to read out of it.
        :return: That file's contents on that branch.
        """
        return self.run_git("show", f"{remote}/{branch}:{name}") + "\n"

    def commit_on_the_fork(self, branch: str) -> str:
        """
        Read a branch from the fork itself rather than from this clone's view of it.

        :param branch: The branch to read.
        :return: The commit the fork has that branch pointing at.
        """
        return self.run_git(
            "ls-remote", RemoteName.ORIGIN, f"refs/heads/{branch}"
        ).split()[0]

    @property
    def git(self) -> GitCommandRunner:
        """
        :return: The runner the executor drives this checkout through.
        """
        return GitCommandRunner(working_directory=self.project_root)
