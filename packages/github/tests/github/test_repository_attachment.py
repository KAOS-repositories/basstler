"""
Tests for :mod:`basstler.github.repository_attachment`: telling a cloud session to
attach a repository it cannot reach.
"""

from __future__ import annotations

from basstler.github.repository import Repository
from basstler.github.repository_attachment import RepositoryAttachment
from basstler.session_tool import BuiltInTool, CloudSessionTool

ATTACHMENT = RepositoryAttachment(
    Repository.parse("an-owner/a-repository"),
    retry_command="run-it-again",
    benefit="the stand-in benefit",
)
"""
The attachment every test renders.
"""

# %% the instruction


def test_the_session_is_told_to_attach_the_repository_with_push_access():
    instruction = ATTACHMENT.instruction()

    assert CloudSessionTool.ATTACH_REPOSITORY in instruction
    assert ATTACHMENT.repository.owner in instruction
    assert ATTACHMENT.repository.name in instruction


def test_a_refused_attach_is_put_to_the_user_with_attaching_recommended():
    instruction = ATTACHMENT.instruction()

    assert BuiltInTool.ASK_USER in instruction
    assert ATTACHMENT.recommended_option in instruction
    assert ATTACHMENT.benefit in instruction


def test_the_command_to_run_once_attached_is_named():
    assert ATTACHMENT.retry_command in ATTACHMENT.instruction()


def test_the_session_is_told_to_skip_the_clone_and_registration_the_attach_asks_for():
    """
    Only the attachment's credential is needed; a clone takes minutes and registering it
    is refused by the session's permission check.
    """
    assert CloudSessionTool.REGISTER_REPOSITORY_ROOT in ATTACHMENT.instruction()
