"""
The skills a playbook ships, each declared as a class of its own, and the ``SKILL.md``
built from each.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from basstler.class_property import classproperty
from basstler.generated_file import GeneratedFile
from basstler.locations import InstructionsTemplate, PluginSkillLocation, SkillLocation
from basstler.playbook.component import PlaybookComponent
from basstler.plugin_root import PluginRoot
from basstler.render_common import create_template_environment
from basstler.session_tool import SessionTool
from basstler.text_file import TextFile


class MarkdownMarkup(StrEnum):
    """
    The Markdown markup that sets a ``SKILL.md``'s generated part apart from its body.
    """

    FRONTMATTER_DELIMITER = "---\n"
    """
    The line above and below the file's YAML frontmatter.
    """

    TITLE_MARKER = "# "
    """
    What starts the file's title line.
    """


# %% skills


@dataclass(frozen=True)
class Skill(PlaybookComponent, ABC):
    """
    A skill, declared as a class whose name is its topic followed by ``Skill``.
    """

    @classproperty
    def topic_words(cls) -> list[str]:
        """
        The words of the topic as the class name spells them, an acronym such as ``PR``
        counting as one word.
        """
        return re.findall(
            r"[A-Z]+(?![a-z])|[A-Z][a-z0-9]*", cls.__name__.removesuffix("Skill")
        )

    @classproperty
    def skill_name(cls) -> str:
        """
        The name a user invokes the skill by, which is also its directory's name: the
        words of its topic in lower case, joined by hyphens.
        """
        return "-".join(word.lower() for word in cls.topic_words)

    @classproperty
    def title(cls) -> str:
        """
        The heading of the skill's instructions: the words of its topic in sentence
        case, keeping acronyms in capitals.
        """
        first_word, *other_words = cls.topic_words
        return " ".join(
            [
                first_word,
                *(word if word.isupper() else word.lower() for word in other_words),
            ]
        )

    @classproperty
    @abstractmethod
    def description(cls) -> str:
        """
        When to use the skill, which Claude reads to decide whether to load it.
        """

    @classproperty
    @abstractmethod
    def allowed_tools(cls) -> tuple[SessionTool, ...]:
        """
        The tools Claude may use without asking while it follows the skill.
        """

    def directory(self, plugin_root: PluginRoot) -> Path:
        """
        :param plugin_root: The plugin.
        :return: The skill's directory in it.
        """
        return plugin_root.path_of(PluginSkillLocation.SKILLS) / self.skill_name

    def instructions_path(self, plugin_root: PluginRoot) -> Path:
        """
        :param plugin_root: The plugin.
        :return: The skill's ``SKILL.md`` in it.
        """
        return self.directory(plugin_root) / SkillLocation.INSTRUCTIONS


# %% the instructions built from a skill


@dataclass(frozen=True)
class SkillInstructions(GeneratedFile):
    """
    The ``SKILL.md`` Claude Code loads one skill from.
    """

    plugin_root: PluginRoot
    """
    The plugin shipping the skill.
    """

    skill: Skill
    """
    The skill the file instructs.
    """

    @property
    def path(self) -> Path:
        return self.skill.instructions_path(self.plugin_root)

    @property
    def text(self) -> str:
        template = create_template_environment().get_template(
            InstructionsTemplate.SKILL.name
        )
        return template.render(skill=self.skill, markup=MarkdownMarkup, body=self.body)

    @property
    def body(self) -> str:
        """
        The hand-written instructions the file holds below its frontmatter and its
        title, either of which it may lack.
        """
        text = TextFile(self.path).read()
        if text.startswith(MarkdownMarkup.FRONTMATTER_DELIMITER):
            text = text.split(MarkdownMarkup.FRONTMATTER_DELIMITER, 2)[2]
        text = text.lstrip("\n")
        if text.startswith(MarkdownMarkup.TITLE_MARKER):
            text = text.partition("\n")[2]
        return text.lstrip("\n")
