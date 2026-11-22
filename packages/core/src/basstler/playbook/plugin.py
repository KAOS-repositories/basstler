"""
The skills and hooks of the Claude Code plugin, and the plugin files built from them.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import ModuleType
from typing import Annotated, Any, Literal

from pydantic import Field, TypeAdapter

from basstler.class_property import classproperty
from basstler.json_model import ValidatedJSONModel
from basstler.locations import (
    ClaudeCodeVariable,
    PackageLocation,
    PluginLocation,
    PluginSkillLocation,
    SkillLocation,
)
from basstler.playbook.component import PlaybookComponent
from basstler.playbook.playbook import Playbook
from basstler.plugin_root import PluginRoot
from basstler.text_file import TextFile

# %% skills


@dataclass(frozen=True)
class SkillDefinition(PlaybookComponent):
    """
    A skill the plugin ships, as a directory of its own under the plugin's skills.
    """

    skill_name: str
    """
    The skill's name, which is also its directory's name and how a user invokes it.
    """

    def directory(self, plugin_root: PluginRoot) -> Path:
        """
        :param plugin_root: The plugin.
        :return: The skill's directory in it.
        """
        return plugin_root.path_of(PluginSkillLocation.SKILLS) / self.skill_name


# %% hooks


class HookEvent(StrEnum):
    """
    The Claude Code events a plugin hook runs on, in the order the plugin lists them.
    """

    SESSION_START = "SessionStart"
    """
    A session starts or resumes.
    """

    STOP = "Stop"
    """
    A turn ends.
    """

    PRE_TOOL_USE = "PreToolUse"
    """
    A tool is about to run; the hook may allow, ask about or deny the call.
    """


@dataclass(frozen=True)
class HookCommand(ABC):
    """
    What a hook runs, written as the plugin's hook registration spells it.
    """

    @property
    @abstractmethod
    def command_line(self) -> str:
        """
        The command, with the plugin's root left for Claude Code to substitute.
        """

    @classproperty
    def plugin_root_placeholder(cls) -> str:
        """
        What Claude Code replaces with the plugin's root in a hook's command.
        """
        return f"${{{ClaudeCodeVariable.PLUGIN_ROOT}}}"


@dataclass(frozen=True)
class PluginScriptCommand(HookCommand):
    """
    One of the plugin's own scripts, run with no arguments.
    """

    script: PluginLocation
    """
    The script, relative to the plugin's root.
    """

    @property
    def command_line(self) -> str:
        return f"{self.plugin_root_placeholder}/{self.script.as_posix()}"


@dataclass(frozen=True)
class PackageModuleCommand(HookCommand):
    """
    A module of the basstler package, run through the plugin's entry point once the
    package is ready.
    """

    module: ModuleType
    """
    The module, which runs as ``python -m``.
    """

    @property
    def command_line(self) -> str:
        module_name = self.module.__spec__.name.removeprefix(
            f"{PackageLocation.DIRECTORY.name}."
        )
        return (
            f"{self.plugin_root_placeholder}/"
            f"{PluginLocation.ENTRY_POINT_SCRIPT.as_posix()} {module_name}"
        )


@dataclass(frozen=True)
class HookDefinition(PlaybookComponent, ABC):
    """
    A hook the plugin registers with Claude Code; each event it can run on is a
    subclass, holding the fields that event accepts.
    """

    command: HookCommand
    """
    What it runs.
    """

    @classproperty
    @abstractmethod
    def event(cls) -> HookEvent:
        """
        The event the hook runs on.
        """

    @property
    def matcher_group(self) -> HookMatcherGroup:
        """
        This hook as one entry of its event's list in the plugin's hook registrations.
        """
        return HookMatcherGroup((HookHandler(self.command.command_line),))


@dataclass(frozen=True)
class SessionStartHook(HookDefinition):
    """
    A hook that runs when a session starts or resumes.
    """

    @classproperty
    def event(cls) -> HookEvent:
        return HookEvent.SESSION_START


@dataclass(frozen=True)
class StopHook(HookDefinition):
    """
    A hook that runs when a turn ends.
    """

    @classproperty
    def event(cls) -> HookEvent:
        return HookEvent.STOP


@dataclass(frozen=True)
class PreToolUseHook(HookDefinition):
    """
    A hook that runs before a tool call, and may allow, ask about or deny it.
    """

    matcher: str | None = None
    """
    The tool names it runs for, as Claude Code matches them; ``None`` for every one.
    """

    condition: str | None = None
    """
    The tool calls it runs for, as a Claude Code permission rule; ``None`` for every
    call the matcher lets through.
    """

    @classproperty
    def event(cls) -> HookEvent:
        return HookEvent.PRE_TOOL_USE

    @property
    def matcher_group(self) -> HookMatcherGroup:
        """
        :meth:`HookDefinition.matcher_group`, limited to :attr:`matcher` and
        :attr:`condition`.
        """
        handler = HookHandler(self.command.command_line, self.condition)
        return HookMatcherGroup((handler,), self.matcher)


# %% the hook registrations file


class HookHandler(ValidatedJSONModel):
    """
    One command Claude Code runs for a hook.
    """

    command: str
    """
    The command line, with the plugin's root left for Claude Code to substitute.
    """

    condition: Annotated[str | None, Field(alias="if")] = None
    """
    The tool calls it runs for, as a Claude Code permission rule; ``None`` for every
    call its group matches.
    """

    handler_kind: Annotated[Literal["command"], Field(alias="type")] = "command"
    """
    How Claude Code runs it: as a shell command.
    """


class HookMatcherGroup(ValidatedJSONModel):
    """
    The handlers Claude Code runs for the tools one matcher selects.
    """

    hooks: tuple[HookHandler, ...]
    """
    The handlers, run in order.
    """

    matcher: str | None = None
    """
    The tool names the group runs for; ``None`` for every one.
    """


class HookRegistrations(ValidatedJSONModel):
    """
    The plugin's hook registrations file, which Claude Code reads the plugin's hooks
    from.
    """

    hooks: dict[HookEvent, tuple[HookMatcherGroup, ...]]
    """
    The groups each event runs, for the events that run any.
    """

    def to_json(self) -> dict[str, Any]:
        """
        :meth:`ValidatedJSONModel.to_json`, leaving out the keys whose value is unset,
        which Claude Code reads as their default.
        """
        return TypeAdapter(type(self)).dump_python(
            self, mode="json", by_alias=True, exclude_none=True
        )

    @property
    def text(self) -> str:
        """
        The file's text.
        """
        return json.dumps(self.to_json(), indent=2) + "\n"


# %% the plugin's files


@dataclass(frozen=True)
class PluginFiles:
    """
    The files of a plugin that follow from a playbook's skills and hooks.
    """

    plugin_root: PluginRoot
    """
    The plugin whose files these are.
    """

    skills: tuple[SkillDefinition, ...]
    """
    The skills the plugin has to ship.
    """

    hooks: tuple[HookDefinition, ...]
    """
    The hooks the plugin has to register, in order within each event.
    """

    @classmethod
    def from_playbook(cls, plugin_root: PluginRoot, playbook: Playbook) -> PluginFiles:
        """
        :param plugin_root: The plugin.
        :param playbook: The playbook whose skills and hooks the plugin follows.
        :return: The plugin's files for that playbook.
        """
        return cls(
            plugin_root,
            playbook.components_of(SkillDefinition),
            playbook.components_of(HookDefinition),
        )

    @property
    def hook_registrations_path(self) -> Path:
        """
        The plugin's hook registrations file.
        """
        return self.plugin_root.path_of(PluginLocation.HOOK_REGISTRATIONS)

    @property
    def hook_registrations(self) -> HookRegistrations:
        """
        The registrations the file must hold: every hook, grouped by event in
        :class:`HookEvent` order.
        """
        groups = {
            event: tuple(
                hook.matcher_group for hook in self.hooks if hook.event == event
            )
            for event in HookEvent
        }
        return HookRegistrations(
            {event: entries for event, entries in groups.items() if entries}
        )

    def shipped_skill_names(self) -> Iterator[str]:
        """
        :return: The name of every directory under the plugin's skills that carries a
            skill's instructions.
        """
        skills_directory = self.plugin_root.path_of(PluginSkillLocation.SKILLS)
        for directory in sorted(skills_directory.iterdir()):
            if (directory / SkillLocation.INSTRUCTIONS).is_file():
                yield directory.name

    @property
    def undeclared_skill_names(self) -> tuple[str, ...]:
        """
        The skills the plugin ships that no :class:`SkillDefinition` declares.
        """
        declared = {skill.skill_name for skill in self.skills}
        return tuple(
            name for name in self.shipped_skill_names() if name not in declared
        )

    @property
    def missing_skills(self) -> tuple[SkillDefinition, ...]:
        """
        The declared skills whose directory carries no instructions.
        """
        return tuple(
            skill
            for skill in self.skills
            if not (
                skill.directory(self.plugin_root) / SkillLocation.INSTRUCTIONS
            ).is_file()
        )

    def hook_registrations_are_current(self) -> bool:
        """
        :return: Whether the hook registrations exist and equal
            :attr:`hook_registrations`' text.
        """
        if not self.hook_registrations_path.is_file():
            return False
        current = TextFile(self.hook_registrations_path).read()
        return current == self.hook_registrations.text

    def write_hook_registrations(self) -> None:
        """
        Write the hook registrations, replacing whatever they held.
        """
        TextFile(self.hook_registrations_path).write(self.hook_registrations.text)
