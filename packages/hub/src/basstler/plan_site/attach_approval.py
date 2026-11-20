"""
Allow a cloud session to attach the user's own plan repositories without a prompt: the hook
Claude Code runs before ``add_repo``, which says nothing for any other repository.

Usage:
    "${BASSTLER_PYTHON}" -m basstler.plan_site.attach_approval < <hook input>
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Annotated

from cyclopts import App
from pydantic import Field

from basstler.exit_codes import StackExitCode
from basstler.github.repository import Repository
from basstler.github.repository_attachment import SessionTool
from basstler.json_model import ValidatedJSONModel
from basstler.locations import ClaudeCodeVariable
from basstler.personal_notes.access import NotesRepositoryAccess
from basstler.plan_site.build_start import recorded_site

# %% what Claude Code sends and expects


class HookEvent(StrEnum):
    """
    The Claude Code events a hook answers.
    """

    PRE_TOOL_USE = "PreToolUse"
    """
    Before a tool runs.
    """


class PermissionDecision(StrEnum):
    """
    What a hook decides about a tool call.
    """

    ALLOW = "allow"
    """
    Run the tool without asking.
    """


class AttachArguments(ValidatedJSONModel):
    """
    The repository a call of :attr:`SessionTool.ATTACH_REPOSITORY` asks for.
    """

    owner: str
    """
    The user or organisation owning the repository.
    """

    repo: str
    """
    The repository's own name.
    """

    @property
    def repository(self) -> Repository:
        """
        The repository asked for.
        """
        return Repository(self.owner, self.repo)


class ToolCall(ValidatedJSONModel):
    """
    The input Claude Code gives a ``PreToolUse`` hook.
    """

    tool_name: str
    """
    The tool about to run.
    """

    tool_input: AttachArguments
    """
    The tool's arguments, read as those of :attr:`SessionTool.ATTACH_REPOSITORY`.
    """


class AllowedAttach(ValidatedJSONModel):
    """
    The part of a hook's answer that decides the tool call.
    """

    reason: Annotated[str, Field(alias="permissionDecisionReason")]
    """
    Why the call is allowed, shown to the user.
    """

    event: Annotated[HookEvent, Field(alias="hookEventName")] = HookEvent.PRE_TOOL_USE
    """
    The event the answer is for.
    """

    decision: Annotated[PermissionDecision, Field(alias="permissionDecision")] = (
        PermissionDecision.ALLOW
    )
    """
    What is decided.
    """


class AttachAnswer(ValidatedJSONModel):
    """
    What the hook prints to allow an attach.
    """

    allowed: Annotated[AllowedAttach, Field(alias="hookSpecificOutput")]
    """
    The decision, under the key Claude Code reads it from.
    """


# %% the repositories


@dataclass(frozen=True)
class PlanRepositories:
    """
    The repositories holding the user's plans, which a session may attach unasked.
    """

    site: Repository | None
    """
    The repository that builds and serves the plan site, ``None`` when no plan site
    lists this clone.
    """

    notes: Repository | None
    """
    The repository the personal-notes branch lives in, ``None`` when none is named.
    """

    @classmethod
    def of_clone(cls, project_root: Path) -> PlanRepositories:
        """
        :param project_root: The clone whose settings and notes branch to read.
        :return: The repositories its notes record.
        """
        site = recorded_site()
        notes = NotesRepositoryAccess.of_clone(project_root, os.environ)
        return cls(
            None if site is None else site.repository,
            None if notes is None else notes.notes_repository,
        )

    def permit(self, call: ToolCall) -> AttachAnswer | None:
        """
        :param call: The tool call about to run.
        :return: The answer allowing it when it attaches one of these repositories,
            ``None`` to leave the decision to the normal permission flow.
        """
        if call.tool_name != SessionTool.ATTACH_REPOSITORY:
            return None
        asked = call.tool_input.repository
        if not any(
            known is not None and known.full_name.lower() == asked.full_name.lower()
            for known in (self.site, self.notes)
        ):
            return None
        return AttachAnswer(
            AllowedAttach(f"{asked.full_name} holds this user's plans or plan site")
        )


# %% the command line

app = App(help=__doc__)
"""
The command, which reads the hook input from standard input.
"""


@app.default
def answer_hook() -> StackExitCode:
    """
    Print the answer allowing the attach on standard output, and nothing when the
    repository is not one of the user's plan repositories.

    :return: :attr:`StackExitCode.SUCCESS`, also when nothing is printed.
    """
    call = ToolCall.from_json(json.loads(sys.stdin.read()))
    project_root = Path(
        os.environ.get(ClaudeCodeVariable.PROJECT_DIRECTORY, Path.cwd())
    )
    answer = PlanRepositories.of_clone(project_root).permit(call)
    if answer is not None:
        sys.stdout.write(json.dumps(answer.to_json()))
    return StackExitCode.SUCCESS


if __name__ == "__main__":
    app()
