"""
GitHub's answer refusing a call, and a stand-in for its REST API that answers each path
with a canned body.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Any

from basstler.github.client import (
    GitHubAttemptClient,
    GitHubResponse,
    GitHubWrite,
    HttpMethod,
)

from basstler.github.credential import CredentialProvider
from basstler.github.exceptions import GitHubRequestFailed

# %% the refusal


def refusal(status: HTTPStatus, method: HttpMethod, path: str) -> GitHubResponse:
    """
    :param status: The status GitHub refuses the call with.
    :param method: The call's method.
    :param path: The call's path.
    :return: GitHub's answer refusing the call.
    """
    return GitHubResponse(
        None,
        failure=GitHubRequestFailed(
            status=status,
            detail="",
            method=method,
            path=path,
            credential_origin=CredentialProvider.CALLER,
        ),
    )


# %% the stand-in


@dataclass
class PathAnsweringClient(GitHubAttemptClient):
    """
    Answers each path read with its canned body, refusing a path it has no answer for,
    and accepts every write unless told to refuse it.
    """

    answers: dict[str, Any] = field(default_factory=dict)
    """
    The body each readable path is answered with.
    """

    forbidden: set[str] = field(default_factory=set)
    """
    The paths refused as forbidden rather than as not found.
    """

    write_answers: dict[str, Any] = field(default_factory=dict)
    """
    The body each write path is answered with, ``None`` for any other.
    """

    write_refusal: HTTPStatus | None = None
    """
    The status every write is refused with, ``None`` to accept them.
    """

    refused_writes: set[str] = field(default_factory=set)
    """
    The write paths refused as forbidden, whatever :attr:`write_refusal` is.
    """

    sent: list[GitHubWrite] = field(default_factory=list)
    """
    Every write sent, oldest first.
    """

    def attempt_get(self, path: str) -> GitHubResponse:
        if path in self.forbidden:
            return refusal(HTTPStatus.FORBIDDEN, HttpMethod.GET, path)
        if path in self.answers:
            return GitHubResponse(self.answers[path])
        return refusal(HTTPStatus.NOT_FOUND, HttpMethod.GET, path)

    def attempt_send(self, write: GitHubWrite) -> GitHubResponse:
        self.sent.append(write)
        if write.path in self.refused_writes:
            return refusal(HTTPStatus.FORBIDDEN, write.method, write.path)
        if self.write_refusal is not None:
            return refusal(self.write_refusal, write.method, write.path)
        return GitHubResponse(self.write_answers.get(write.path))
