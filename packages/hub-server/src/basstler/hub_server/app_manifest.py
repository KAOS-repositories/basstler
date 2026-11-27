"""
The App manifest: what the App may read, which events it receives and, for one
instance, where it is reached.
"""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Annotated, Self

from pydantic import Field

from basstler.github.permission_level import PermissionLevel
from basstler.json_model import ValidatedJSONModel
from basstler.locations import HubServerTemplate
from basstler.text_file import TextFile

APP_NAME_LIMIT = 34
"""
The most characters GitHub allows in an App's name.
"""

# %% what the manifest names


class AppPermission(StrEnum):
    """
    A permission an App can be granted.
    """

    METADATA = "metadata"
    """
    Repositories' basic information.
    """

    CONTENTS = "contents"
    """
    Repositories' files and commits.
    """

    PULL_REQUESTS = "pull_requests"
    """
    Pull requests, their reviews and their comments.
    """

    CHECKS = "checks"
    """
    Check runs and check suites.
    """

    STATUSES = "statuses"
    """
    Commit statuses.
    """


class AppEvent(StrEnum):
    """
    An event GitHub delivers to the App's webhook.
    """

    PUSH = "push"
    """
    Commits pushed to a branch or tag.
    """

    PULL_REQUEST = "pull_request"
    """
    A pull request opened, closed, edited or otherwise changed.
    """

    PULL_REQUEST_REVIEW = "pull_request_review"
    """
    A pull request review submitted, edited or dismissed.
    """

    PULL_REQUEST_REVIEW_THREAD = "pull_request_review_thread"
    """
    A review thread of a pull request resolved or unresolved.
    """

    CHECK_SUITE = "check_suite"
    """
    A check suite requested, completed or rerequested.
    """

    STATUS = "status"
    """
    A commit's status changed.
    """

    ISSUE_COMMENT = "issue_comment"
    """
    A comment on an issue or pull request.
    """

    INSTALLATION_REPOSITORIES = "installation_repositories"
    """
    Repositories added to or removed from the App's installation.
    """


# %% what is committed


class AppCapabilities(ValidatedJSONModel):
    """
    What the App may read and which events it receives: the part of the manifest every
    instance shares.
    """

    public: bool
    """
    Whether anyone, not only the owner, can install the App.
    """

    default_permissions: dict[AppPermission, PermissionLevel]
    """
    The access the App is granted on each permission.
    """

    default_events: tuple[AppEvent, ...]
    """
    The events the App subscribes to.
    """

    @classmethod
    def committed(cls) -> AppCapabilities:
        """
        :return: The capabilities the package ships.
        """
        return AppCapabilities.from_json(
            json.loads(TextFile(HubServerTemplate.APP_MANIFEST).read())
        )


# %% what an instance registers


class HookAttributes(ValidatedJSONModel):
    """
    Where GitHub delivers the App's events.
    """

    url: str
    """
    The address of the instance's webhook.
    """

    active: bool = True
    """
    Whether GitHub delivers events.
    """


class AppManifest(AppCapabilities):
    """
    The manifest one instance submits to GitHub to register its App.
    """

    name: Annotated[str, Field(max_length=APP_NAME_LIMIT)]
    """
    The App's name, unique across GitHub.
    """

    url: str
    """
    The App's home page.
    """

    hook_attributes: HookAttributes
    """
    Where GitHub delivers the App's events.
    """

    redirect_url: str
    """
    Where GitHub sends the browser once the App is registered.
    """

    @classmethod
    def from_committed(
        cls, name: str, homepage_url: str, webhook_url: str, redirect_url: str
    ) -> Self:
        """
        :param name: The App's name.
        :param homepage_url: The App's home page.
        :param webhook_url: Where GitHub delivers the App's events.
        :param redirect_url: Where GitHub sends the browser once the App is registered.
        :return: The committed capabilities with the instance's name and addresses.
        """
        capabilities = AppCapabilities.committed()
        return cls(
            public=capabilities.public,
            default_permissions=capabilities.default_permissions,
            default_events=capabilities.default_events,
            name=name,
            url=homepage_url,
            hook_attributes=HookAttributes(url=webhook_url),
            redirect_url=redirect_url,
        )

    @staticmethod
    def default_name(owner: str) -> str:
        """
        :param owner: The account or organization that registers the App.
        :return: A name unique to the owner.
        """
        return f"{owner}-basstlerhub"
