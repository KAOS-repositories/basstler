"""
The requests GitHub's pull request endpoints read.
"""

from __future__ import annotations

from basstler.git.branch import Branch
from basstler.class_property import classproperty
from pydantic import field_serializer

from basstler.github.client import GitHubWrite, HttpMethod
from basstler.github.issue import IssueWrite
from basstler.github.pull_request_ends import PullRequestOpening
from basstler.github.repository import Repository

# %% opening a pull request


class NewPullRequest(GitHubWrite, PullRequestOpening):
    """
    A pull request that does not exist yet, opened on its base's repository.
    """

    draft: bool = True
    """
    Whether it opens as a draft, which a pull request stays until its author has
    reviewed it themselves.
    """

    @classproperty
    def method(cls) -> HttpMethod:
        return HttpMethod.POST

    @property
    def path(self) -> str:
        return self.base.repository.pull_requests_path

    @field_serializer("base")
    def _base_name(self, base: Branch[Repository]) -> str:
        """
        :param base: :attr:`base`.
        :return: Its name, as the endpoint takes it.
        """
        return base.name

    @field_serializer("head")
    def _head_name(self, head: Branch[Repository]) -> str:
        """
        :param head: :attr:`head`.
        :return: Its name as the base's repository names it.
        """
        return self.base.repository.head_name(head)


# %% editing a pull request


class PullRequestDescription(IssueWrite):
    """
    A pull request's new description, leaving everything else about it unchanged.
    """

    body: str
    """
    The description, in Markdown.
    """

    @classproperty
    def method(cls) -> HttpMethod:
        return HttpMethod.PATCH

    @property
    def path(self) -> str:
        return self.repository.pull_request_path(self.number)
