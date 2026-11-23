"""
The basstler modules and skills a document cites, and which of them this release no
longer ships.

Usage:
    "${BASSTLER_PYTHON}" -m basstler.document_references <document>...
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from collections.abc import Mapping
from enum import Enum, StrEnum
from functools import cache
from types import MappingProxyType
from importlib.metadata import version
from itertools import takewhile
from pathlib import Path

from cyclopts import App

from basstler.class_property import classproperty
from basstler.locations import PackageLocation, PluginLocation, WorkspaceLocation
from basstler.package_layout import package_modules
from basstler.package_map import Distribution
from basstler.regular_expression import (
    Anchor,
    CharacterClass,
    CharacterRange,
    CharacterSet,
    RegularExpression,
    Separator,
)
from basstler.slash_command import SlashCommand
from basstler.standard_streams import StandardStreamHandler
from basstler.text_file import TextFile

logger = StandardStreamHandler.logger_for(__name__)
"""
This module's logger, which is also what its command prints through.
"""

# %% what a document cites

PACKAGE_NAME = PackageLocation.DIRECTORY.name
"""
The package every cited module belongs to.
"""


class CitationGroup(StrEnum):
    """
    The part of a citation read back from its match.
    """

    CITED_NAME = "cited_name"
    """
    The module or skill cited.
    """


@dataclass(frozen=True)
class Retirement:
    """
    What replaced a retired skill, and the major release that retired it.
    """

    replacement: str
    """
    What to cite or do instead.
    """

    major_version: int
    """
    The major release that retired the skill; the next major release no longer
    reports it.
    """


class RetiredSkill(Enum):
    """
    A skill the plugin once shipped and no longer does.
    """

    @property
    def invoked_as(self) -> str:
        """
        The slash command that invoked it.
        """
        return "/" + self._name_.lower().replace("_", "-")

    @classmethod
    def retirements(cls) -> dict[str, Retirement]:
        """
        :return: Each retired skill's retirement, by the skill's name without the slash.
        """
        return {skill.invoked_as.removeprefix("/"): skill.value for skill in cls}


@dataclass(frozen=True)
class StaleReference:
    """
    One name a document cites that this release does not ship.
    """

    cited: str
    """
    The name as a session would run it: a module's import path, or a slash command.
    """

    replacement: str | None
    """
    What to cite or do instead, ``None`` when nothing shipped takes its place.
    """

    def as_line(self) -> str:
        """:return: The reference and its replacement, as one line."""
        if self.replacement is None:
            return f"{self.cited}: not shipped, and nothing replaces it"
        return f"{self.cited}: not shipped; {self.replacement}"


# %% what the package ships


@dataclass(frozen=True)
class ShippedModules:
    """
    Every module and subpackage of the installed package, named below the package.
    """

    modules: frozenset[str]
    """
    Every module's dotted name, e.g. ``"plan.manifest_tools"``.
    """

    major_version: int
    """
    The major release these modules belong to.
    """

    @classmethod
    @cache
    def installed(cls) -> ShippedModules:
        """:return: The modules and major release of the package this runs from."""
        return cls(
            frozenset(module.name for module in package_modules()),
            int(version(Distribution.NOTES).partition(".")[0]),
        )

    @property
    def subpackages(self) -> frozenset[str]:
        """
        Every package that holds a module, by its dotted name.
        """
        return frozenset(
            ".".join(parts[:end])
            for parts in (module.split(".") for module in self.modules)
            for end in range(1, len(parts))
        )

    def ships(self, cited: str) -> bool:
        """
        :param cited: A dotted name below the package, its classes already removed.
        :return: Whether it is a module or subpackage, or a function of a module.
        """
        parent = cited.rpartition(".")[0]
        return (
            cited in self.modules or cited in self.subpackages or parent in self.modules
        )

    def replacement_for(self, cited: str) -> str | None:
        """
        :param cited: A dotted name below the package that :meth:`ships` refuses.
        :return: The import path of the one module it moved to - the same name with its
            dots and underscores swapped, or else the only module of the same last
            name - or ``None`` when there is no such module.
        """
        flattened = cited.replace(".", "_")
        renamed = [
            module for module in self.modules if module.replace(".", "_") == flattened
        ]
        last_name = cited.rpartition(".")[2]
        same_last_name = [
            module for module in self.modules if module.rpartition(".")[2] == last_name
        ]
        moved_to = renamed or same_last_name
        if len(moved_to) != 1:
            return None
        return f"{PACKAGE_NAME}.{moved_to[0]}"


# %% reading a document


@dataclass(frozen=True)
class CitedNames:
    """
    The package's modules and the slash commands one document cites.
    """

    modules: frozenset[str]
    """
    Every cited module's dotted name below the package, without any class or method
    named after it.
    """

    skills: frozenset[str]
    """
    Every skill a cited slash command invokes, without the slash.
    """

    @classproperty
    def identifier(cls) -> RegularExpression:
        """
        A Python name.

        >>> CitedNames.identifier.compiled().match("size_limits.py")[0]
        'size_limits'
        """
        return RegularExpression.sequence(
            CharacterSet.any_of(
                CharacterRange.ASCII_LETTER,
                "_",
            ),
            CharacterClass.WORD_CHARACTER.zero_or_more(),
        )

    @classproperty
    def module_name(cls) -> RegularExpression:
        """
        A Python name in lower case, as a module is named.

        >>> pattern = CitedNames.module_name.compiled()
        >>> pattern.match("model.PlanDocument")[0]
        'model'
        """
        return RegularExpression.sequence(
            CharacterSet.any_of(CharacterRange.ASCII_LOWERCASE_LETTER, "_"),
            CharacterClass.WORD_CHARACTER.zero_or_more(),
        )

    @classproperty
    def name_continuation(cls) -> RegularExpression:
        """
        A character that would continue a name, so the name before it is not the whole
        name.

        >>> CitedNames.name_continuation.compiled().findall("a-b.c")
        ['a', '-', 'b', 'c']
        """
        return CharacterSet.any_of(CharacterClass.WORD_CHARACTER, "-")

    @classproperty
    def dotted_citation(cls) -> re.Pattern[str]:
        """
        A dotted import path into the package, capturing it below the package.

        >>> pattern = CitedNames.dotted_citation
        >>> pattern.findall("run basstler.plan.model or my-basstler.plan")
        ['plan.model']
        """
        return RegularExpression.sequence(
            RegularExpression.negative_lookbehind(
                CharacterSet.any_of(CharacterClass.WORD_CHARACTER, "./-")
            ),
            RegularExpression.negative_lookahead(
                RegularExpression.sequence(
                    PluginLocation.ENTRY_POINT_SCRIPT.name, Anchor.WORD_BOUNDARY
                )
            ),
            f"{PACKAGE_NAME}.",
            RegularExpression.sequence(
                cls.identifier,
                RegularExpression.sequence(".", cls.identifier).zero_or_more(),
            ).captured_as(CitationGroup.CITED_NAME),
            RegularExpression.negative_lookahead(cls.name_continuation),
        ).compiled()

    @classproperty
    def source_file_citation(cls) -> re.Pattern[str]:
        """
        A source file of the package, capturing its path below the package directory.

        >>> CitedNames.source_file_citation.findall("see src/basstler/plan/model.py")
        ['plan/model']
        """
        return RegularExpression.sequence(
            Anchor.WORD_BOUNDARY,
            f"{WorkspaceLocation.PACKAGE_SOURCE.as_posix()}/",
            CharacterSet.any_of(CharacterClass.WORD_CHARACTER, "/")
            .one_or_more()
            .captured_as(CitationGroup.CITED_NAME),
            ".py",
            Anchor.WORD_BOUNDARY,
        ).compiled()

    @classproperty
    def entry_point_citation(cls) -> re.Pattern[str]:
        """
        The module the plugin's entry point script is asked to run, the script written
        as a command: after its path, a quote or a backtick, never as a word of prose.

        >>> pattern = CitedNames.entry_point_citation
        >>> pattern.findall('"${CLAUDE_PLUGIN_ROOT}/hooks/basstler.sh" setup.gate')
        ['setup.gate']
        >>> pattern.findall("the basstler.sh script")
        []
        """
        return RegularExpression.sequence(
            RegularExpression.lookbehind(CharacterSet.any_of('/"`')),
            PluginLocation.ENTRY_POINT_SCRIPT.name,
            RegularExpression.literal('"').optional(),
            Separator.WHITESPACE.one_or_more(),
            RegularExpression.sequence(
                cls.module_name,
                RegularExpression.sequence(".", cls.module_name).zero_or_more(),
            ).captured_as(CitationGroup.CITED_NAME),
            RegularExpression.negative_lookahead(cls.name_continuation),
        ).compiled()

    @classproperty
    def skill_citation(cls) -> re.Pattern[str]:
        """
        A slash command, capturing the skill it invokes.

        >>> pattern = CitedNames.skill_citation
        >>> pattern.findall("run /plan-create, not a/plan-create or /plan")
        ['plan-create']
        """
        skill_name_word = CharacterSet.any_of(
            CharacterRange.ASCII_LOWERCASE_LETTER, CharacterRange.ASCII_DIGIT
        ).one_or_more()
        return RegularExpression.sequence(
            RegularExpression.negative_lookbehind(
                CharacterSet.any_of(CharacterClass.WORD_CHARACTER, "/.")
            ),
            SlashCommand.PREFIX,
            RegularExpression.sequence(
                CharacterRange.ASCII_LOWERCASE_LETTER,
                CharacterSet.any_of(
                    CharacterRange.ASCII_LOWERCASE_LETTER, CharacterRange.ASCII_DIGIT
                ).zero_or_more(),
                RegularExpression.sequence("-", skill_name_word).one_or_more(),
            ).captured_as(CitationGroup.CITED_NAME),
            RegularExpression.negative_lookahead(
                CharacterSet.any_of(CharacterClass.WORD_CHARACTER, "/-")
            ),
        ).compiled()

    @classmethod
    def in_text(cls, text: str) -> CitedNames:
        """:param text: A document's text.
        :return: The names it cites."""
        dotted = {
            ".".join(takewhile(lambda part: not part[:1].isupper(), name.split(".")))
            for name in cls.dotted_citation.findall(text)
        }
        source_files = {
            path.replace("/", ".") for path in cls.source_file_citation.findall(text)
        }
        entry_points = set(cls.entry_point_citation.findall(text))
        return cls(
            modules=frozenset(
                name for name in dotted | source_files | entry_points if name
            ),
            skills=frozenset(cls.skill_citation.findall(text)),
        )

    def stale(
        self,
        shipped: ShippedModules,
        retirements: Mapping[str, Retirement] = MappingProxyType(
            RetiredSkill.retirements()
        ),
    ) -> list[StaleReference]:
        """
        :param shipped: What the installed package ships.
        :param retirements: Each retired skill's retirement, by the skill's name without
            the slash.
        :return: Every cited name it does not ship, skills retired in its major release
            first, each in name order.
        """
        retired = {
            name: retirement
            for name, retirement in retirements.items()
            if retirement.major_version >= shipped.major_version
        }
        skills = [
            StaleReference(f"/{name}", retired[name].replacement)
            for name in sorted(self.skills & retired.keys())
        ]
        modules = []
        for name in sorted(self.modules):
            if shipped.ships(name):
                continue
            moved_to = shipped.replacement_for(name)
            modules.append(
                StaleReference(
                    f"{PACKAGE_NAME}.{name}",
                    None if moved_to is None else f"now {moved_to}",
                )
            )
        return skills + modules


# %% the command line

app = App(help=__doc__)
"""
The command, which takes the documents to check.
"""


@app.default
def report_stale_references(*documents: Path) -> int:
    """
    Print one line per name the documents cite that this release does not ship.

    :param documents: The documents to check.
    :return: 0, also when a reference is stale: the lines are the report.
    """
    shipped = ShippedModules.installed()
    for document in documents:
        for reference in CitedNames.in_text(TextFile(document).read()).stale(shipped):
            logger.info(reference.as_line())
    return 0


if __name__ == "__main__":
    app()
