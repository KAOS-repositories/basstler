"""
Telling a Claude Code cloud session to attach a repository it cannot reach, and to ask the
user when the attach is refused.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from basstler.github.repository import HasRepository
from basstler.session_tool import SessionTool

# %% the session's proxy


class SessionProxyAnswer(StrEnum):
    """
    What a cloud session's proxy answers a GitHub request with, in GitHub's place.
    """

    REPOSITORY_NOT_ATTACHED = (
        "GitHub access to this repository is not enabled for this session"
    )
    """
    The repository is not attached to the session, whether or not it exists.
    """


# %% the instruction


@dataclass(frozen=True)
class RepositoryAttachment(HasRepository):
    """
    How a cloud session gets :attr:`repository` attached, and what it then runs.
    """

    retry_command: str
    """
    The command that does what failed, once the repository is attached.
    """

    benefit: str
    """
    What attaching the repository gives the user, said when asking them to allow it.
    """

    recommended_option: str = "Attach it (Recommended)"
    """
    The first option the user is offered when the attach is refused.
    """

    def instruction(self) -> str:
        """
        :return: The tool call that attaches :attr:`repository`, the command to run
            then without a local clone, and the question to put to the user when the
            attach is refused.
        """
        return (
            f"Attach {self.repository.full_name} to this session: call "
            f"{SessionTool.ATTACH_REPOSITORY} with owner {self.repository.owner}, repo "
            f"{self.repository.name} and access push, then run {self.retry_command}. "
            f"Only the attachment's credential is needed: skip the clone and the "
            f"{SessionTool.REGISTER_REPOSITORY_ROOT} call the attach answer asks for. If "
            f"the attach is refused, ask the user with {SessionTool.ASK_USER} to allow "
            f'it, with "{self.recommended_option}" as the first option: '
            f"{self.benefit}."
        )
