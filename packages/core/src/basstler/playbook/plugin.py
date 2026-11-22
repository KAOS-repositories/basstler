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
from typing import Any

from basstler.locations import (
    ClaudeCodeVariable,
    PackageLocation,
    PluginLocation,
    PluginSkillLocation,
    SkillLocation,
)
from basstler.playbook.component import PlaybookComponent
from basstler.playbook.playbook import Playbook
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

    def directory(self, plugin_root: Path) -> Path:
        """
        :param plugin_root: The plugin's root directory.
        :return: The skill's directory in it.
        """
        return plugin_root / PluginSkillLocation.SKILLS / self.skill_name


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

    @property
    def plugin_root(self) -> str:
        """
        The plugin's root as Claude Code substitutes it into a hook's command.
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
        return f"{self.plugin_root}/{self.script.as_posix()}"


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
            f"{self.plugin_root}/{PluginLocation.ENTRY_POINT_SCRIPT.as_posix()} "
            f"{module_name}"
        )


@dataclass(frozen=True)
class HookDefinition(PlaybookComponent):
    """
    A hook the plugin registers with Claude Code.
    """

    event: HookEvent
    """
    The event it runs on.
    """

    command: HookCommand
    """
    What it runs.
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

    def registration(self) -> dict[str, Any]:
        """
        :return: This hook as one entry of its event's list in the plugin's hook
            registrations.
        """
        hook: dict[str, Any] = {"type": "command"}
        if self.condition is not None:
            hook["if"] = self.condition
        hook["command"] = self.command.command_line
        entry: dict[str, Any] = {}
        if self.matcher is not None:
            entry["matcher"] = self.matcher
        entry["hooks"] = [hook]
        return entry


# %% the plugin's files


@dataclass(frozen=True)
class PluginFiles:
    """
    The files of a plugin that follow from a playbook's skills and hooks.
    """

    plugin_root: Path
    """
    The plugin's root directory.
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
    def for_playbook(cls, plugin_root: Path, playbook: Playbook) -> PluginFiles:
        """
        :param plugin_root: The plugin's root directory.
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
        The plugin's hook registrations.
        """
        return self.plugin_root / PluginLocation.HOOK_REGISTRATIONS

    @property
    def hook_registrations(self) -> str:
        """
        The text the hook registrations must have: every hook, grouped by event in
        :class:`HookEvent` order.
        """
        registrations = {
            event.value: [
                hook.registration() for hook in self.hooks if hook.event == event
            ]
            for event in HookEvent
        }
        document = {
            "hooks": {
                event: entries for event, entries in registrations.items() if entries
            }
        }
        return json.dumps(document, indent=2) + "\n"

    def shipped_skill_names(self) -> Iterator[str]:
        """
        :return: The name of every directory under the plugin's skills that carries a
            skill's instructions.
        """
        skills_directory = self.plugin_root / PluginSkillLocation.SKILLS
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
            :attr:`hook_registrations`.
        """
        if not self.hook_registrations_path.is_file():
            return False
        return TextFile(self.hook_registrations_path).read() == self.hook_registrations

    def write_hook_registrations(self) -> None:
        """
        Write the hook registrations, replacing whatever they held.
        """
        TextFile(self.hook_registrations_path).write(self.hook_registrations)
