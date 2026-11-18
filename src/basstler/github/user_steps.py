"""
The steps on GitHub only the user can take, each with the browser steps and, where
GitHub offers one, the command that takes it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from basstler.github.workflows import RepositoryWorkflow
from basstler.github.repository import Repository, RepositoryMember

# %% a step


class UserStep(ABC):
    """
    One step only the user can take.
    """

    @property
    @abstractmethod
    def description(self) -> str:
        """
        What the step does, as a phrase.
        """

    @property
    @abstractmethod
    def browser_steps(self) -> tuple[str, ...]:
        """
        The step taken on github.com, one click or entry each, in order.
        """

    @property
    def command(self) -> str | None:
        """
        The command that takes it, ``None`` when GitHub offers none.
        """
        return None

    @property
    def text(self) -> str | None:
        """
        A file the step writes, shown in full, ``None`` when it writes none.
        """
        return None


# %% repository settings


@dataclass(frozen=True)
class AllowActions(RepositoryMember, UserStep):
    """
    Allowing a repository to run Actions.
    """

    known_off: bool
    """
    Whether Actions are known to be off there, rather than unread.
    """

    @property
    def description(self) -> str:
        if self.known_off:
            return f"allow Actions on {self.repository.full_name}"
        return f"check that {self.repository.full_name} allows Actions"

    @property
    def browser_steps(self) -> tuple[str, ...]:
        allow = "Allow all actions and reusable workflows, then click Save."
        return (
            f"Open {self.repository.actions_settings_url}.",
            f"Choose {allow}"
            if self.known_off
            else f"If Actions are disabled there: choose {allow}",
        )


@dataclass(frozen=True)
class EnableWorkflow(RepositoryWorkflow, RepositoryMember, UserStep):
    """
    Enabling one disabled workflow of a repository.
    """

    @property
    def description(self) -> str:
        return f"enable the {self.workflow_path.name} workflow"

    @property
    def browser_steps(self) -> tuple[str, ...]:
        return (
            f"Open {self.repository.workflow_page_url(self.workflow_path)}.",
            "Click Enable workflow.",
        )


# %% pull requests


@dataclass(frozen=True)
class MergePullRequest(UserStep):
    """
    Reviewing and merging an open pull request.
    """

    page_url: str
    """
    The pull request's page.
    """

    change: str
    """
    What the pull request does, as a phrase completing "the pull request ...".
    """

    @property
    def description(self) -> str:
        return f"merge the pull request {self.change}"

    @property
    def browser_steps(self) -> tuple[str, ...]:
        return (f"Open {self.page_url}.", "Review it, then merge it.")


@dataclass(frozen=True)
class OpenPullRequestFromForm(MergePullRequest):
    """
    Opening a pull request from its filled-in form, then merging it.
    """

    @property
    def description(self) -> str:
        return f"open and {super().description}"

    @property
    def browser_steps(self) -> tuple[str, ...]:
        return (
            f"Open {self.page_url} - its title and description are filled in.",
            "Click Create pull request, review it, then merge it.",
        )


# %% forks


@dataclass(frozen=True)
class SyncFork(UserStep):
    """
    Bringing a fork's default branch up to date with its parent's.
    """

    fork: Repository
    """
    The fork.
    """

    @property
    def description(self) -> str:
        return f"sync {self.fork.full_name}'s default branch with its parent's"

    @property
    def browser_steps(self) -> tuple[str, ...]:
        return (f"Open {self.fork.url}.", "Click Sync fork, then Update branch.")

    @property
    def command(self) -> str | None:
        return f"gh repo sync {self.fork.full_name}"
