"""
Tests for :mod:`basstler.plan_site.attach_approval`: allowing a cloud session to attach
the user's own plan repositories without a prompt.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from basstler.github.repository import Repository
from basstler.github.repository_attachment import SessionTool
import basstler.plan_site.attach_approval
from basstler.locations import BasstlerVariable, PluginLocation
from basstler.plan_site.attach_approval import (
    AttachAnswer,
    AttachArguments,
    PermissionDecision,
    PlanRepositories,
    ToolCall,
)

# %% the repositories

SITE = Repository("an-owner", "plans-site")
"""
The repository that builds and serves the plan site.
"""

NOTES = Repository("an-owner", "plans-notes")
"""
The repository holding the personal-notes branch.
"""

PLANS = PlanRepositories(site=SITE, notes=NOTES)
"""
A user whose plan site and notes live in separate repositories.
"""


def attach(
    repository: Repository, tool: str = SessionTool.ATTACH_REPOSITORY
) -> ToolCall:
    """
    :param repository: The repository the call asks to attach.
    :param tool: The tool called.
    :return: The hook input for that call.
    """
    return ToolCall(tool, AttachArguments(repository.owner, repository.name))


# %% allowing an attach


@pytest.mark.parametrize("repository", [SITE, NOTES], ids=["site", "notes"])
def test_attaching_a_plan_repository_is_allowed(repository: Repository):
    """
    Attaching the site or the notes repository is allowed without a prompt.
    """
    answer = PLANS.permit(attach(repository))

    assert answer.allowed.decision is PermissionDecision.ALLOW


def test_the_answer_is_written_under_the_keys_claude_code_reads():
    """
    The decision is written under ``hookSpecificOutput``, with the event and decision
    spelled as Claude Code reads them.
    """
    answer = PLANS.permit(attach(SITE))

    written = answer.to_json()["hookSpecificOutput"]
    assert written["hookEventName"] == answer.allowed.event
    assert written["permissionDecision"] == answer.allowed.decision
    assert SITE.full_name in written["permissionDecisionReason"]


def test_an_answer_reads_back_as_written():
    """
    What the hook prints parses back into the same answer.
    """
    answer = PLANS.permit(attach(NOTES))

    assert AttachAnswer.from_json(answer.to_json()) == answer


def test_the_owner_s_letter_case_does_not_matter():
    """
    GitHub names repositories regardless of letter case, so a differently cased name is
    the same repository.
    """
    shouted = Repository(SITE.owner.upper(), SITE.name.upper())

    assert PLANS.permit(attach(shouted)) is not None


# %% leaving the decision alone


def test_another_repository_is_left_to_the_normal_permission_flow():
    """
    A repository that holds no plans gets no answer, so the user is asked as before.
    """
    assert PLANS.permit(attach(Repository("an-owner", "something-else"))) is None


def test_the_same_name_under_another_owner_is_left_alone():
    """
    A repository is the owner and the name together.
    """
    assert PLANS.permit(attach(Repository("someone-else", SITE.name))) is None


def test_another_tool_is_left_alone():
    """
    Only the attach tool is allowed, whatever its input names.
    """
    assert PLANS.permit(attach(SITE, tool=SessionTool.ASK_USER)) is None


def test_a_user_with_no_recorded_repositories_is_never_allowed_anything():
    """
    With no site and no notes repository recorded, nothing matches.
    """
    assert PlanRepositories(site=None, notes=None).permit(attach(SITE)) is None


# %% registering the hook

HOOK_EVENT = "PreToolUse"
"""
The event the hook is registered under in the plugin's hook manifest.
"""


def test_the_plugin_runs_the_hook_before_the_attach_tool_and_nothing_else():
    """
    The plugin's hook manifest registers this module for the attach tool alone.
    """
    plugin_root = Path(os.environ[BasstlerVariable.PLUGIN_ROOT])
    manifest = json.loads(
        (plugin_root / PluginLocation.HOOKS / "hooks.json").read_text(encoding="utf-8")
    )

    (registration,) = manifest["hooks"][HOOK_EVENT]
    (hook,) = registration["hooks"]
    assert registration["matcher"] == SessionTool.ATTACH_REPOSITORY
    assert hook["command"].endswith(
        f"{PluginLocation.ENTRY_POINT_SCRIPT} "
        f"{basstler.plan_site.attach_approval.__spec__.name.removeprefix('basstler.')}"
    )
