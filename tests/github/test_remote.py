"""
Tests for :class:`GitHubRemote`: the GitHub repository a clone's remote points at.
"""

from __future__ import annotations

from basstler.git.commands import GitCommandRunner
from basstler.github.remote import GitHubRemote
from basstler.github.repository import Repository

from ..maintenance.fork import ForkCheckout, RemoteName

# %% helpers


def fork_remote(checkout: ForkCheckout) -> GitHubRemote:
    """
    :return: The checkout's fork remote.
    """
    return GitHubRemote(GitCommandRunner(checkout.project_root), RemoteName.ORIGIN)


# %% the repository


def test_the_remote_names_the_repository_its_url_points_at(fork_checkout):
    """
    The repository is the one the remote's URL names.
    """
    remote = fork_remote(fork_checkout)

    assert remote.github_repository == Repository.from_remote_url(
        fork_checkout.fork_path.as_uri()
    )


def test_the_remote_is_described_by_its_repository_s_name(fork_checkout):
    """
    A remote naming a repository is described by that repository's full name.
    """
    remote = fork_remote(fork_checkout)

    assert remote.description == remote.github_repository.full_name


def test_a_remote_naming_no_repository_is_described_by_its_location(tmp_path):
    """
    A remote given as a local path names no repository, so its location describes it.
    """
    remote = GitHubRemote(GitCommandRunner(tmp_path), str(tmp_path))

    assert remote.github_repository is None
    assert remote.description == str(tmp_path)
