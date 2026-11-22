"""
Contract test over the skill documents that send a session to the setup prerequisite
check.

The rule they share is stated once, in prerequisite-check.md: a skill whose setup check
fails runs ``/setup-personal-notes`` rather than asking whether to. A document that
instructs an offer instead contradicts it, and nothing else catches that - a branch that
forks the instruction into a new document of its own conflicts with no existing file, so
the contradiction arrives silently at merge time.

Filesystem only: no network, no credentials, no scratch repository.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from basstler.locations import PackageLocation
from basstler.regular_expression import (
    Anchor,
    CharacterClass,
    CharacterRange,
    CharacterSet,
    RegularExpression,
)
from basstler.setup import gate
from basstler.setup.gate import BasstlerSkill, GateOption

from basstler_testing.constants.paths import RepositoryLocation, SkillDirectory


class SkillCommand(StrEnum):
    """
    A skill, as a session is told to invoke it.
    """

    SETUP_PERSONAL_NOTES = "/setup-personal-notes"
    """
    The one-time setup of the personal-notes tooling.
    """


class OfferingVerb(StrEnum):
    """
    The verbs by which a document makes a command something to ask about rather than
    something to run.
    """

    OFFER = "offer"
    """
    The verb the instruction this rule replaced was written with.
    """

    PROPOSE = "propose"
    """
    A synonym that would reinstate the same question.
    """

    SUGGEST = "suggest"
    """
    A synonym that would reinstate the same question.
    """


# %% the documents under test


class VerbEnding(StrEnum):
    """
    The endings an offering verb takes in an instruction.
    """

    THIRD_PERSON = "s"
    """
    As in *offers*.
    """

    PRESENT_PARTICIPLE = "ing"
    """
    As in *offering*.
    """


class InstructionWord(StrEnum):
    """
    The words between an offering verb and the command it offers.
    """

    TO = "to"
    """
    Opens the infinitive, as in *offer to run*.
    """

    RUN = "run"
    """
    The verb an offer to run a command uses.
    """

    CODE_QUOTE = "`"
    """
    Encloses the command as inline code.
    """


class GateGroup(StrEnum):
    """
    The part of a gate command read back from its match.
    """

    SKILL = "skill"
    """
    The skill the gate checks for.
    """


@dataclass(frozen=True)
class SkillDocument:
    """
    One markdown document belonging to a skill, read for the instructions it gives.
    """

    path: Path
    """
    Its location on disk.
    """

    text: str
    """
    Its full contents.
    """

    @classmethod
    def read_from(cls, path: Path) -> SkillDocument:
        """
        Read one document.

        :param path: The document's location on disk.
        :return: The document.
        """
        return cls(path=path, text=path.read_text(encoding="utf-8"))

    @property
    def relative_path(self) -> str:
        """
        The path as a reader of this repository would name it.
        """
        return str(self.path.relative_to(RepositoryLocation.ROOT.value))

    @property
    def offer_instructions(self) -> list[str]:
        """
        Every place this document tells a session to offer the setup rather than run it.
        """
        return [match.group(0) for match in self.offer_pattern().finditer(self.text)]

    @staticmethod
    def offer_pattern() -> re.Pattern[str]:
        """
        The instruction shape the no-ask rule replaced: a verb of offering or proposing,
        governing the setup command directly.

        Deliberately narrow - it is aimed at the sentence that was copied from document to
        document (``offer `/setup-personal-notes```), not at every possible paraphrase of
        asking, and it must not fire on prose *about* the rule, which discusses offering
        and asking at length.
        """
        to_run = RegularExpression.sequence(
            InstructionWord.TO,
            CharacterClass.WHITESPACE.one_or_more(),
            InstructionWord.RUN,
            CharacterClass.WHITESPACE.one_or_more(),
        )
        return (
            RegularExpression.sequence(
                Anchor.WORD_BOUNDARY,
                RegularExpression.either(*OfferingVerb),
                RegularExpression.either(*VerbEnding).optional(),
                CharacterClass.WHITESPACE.one_or_more(),
                to_run.optional(),
                RegularExpression.sequence(InstructionWord.CODE_QUOTE).optional(),
                SkillCommand.SETUP_PERSONAL_NOTES,
            )
            .case_insensitive()
            .compiled()
        )


def skill_documents() -> list[SkillDocument]:
    """
    Every markdown document under the skills directory.

    Discovered rather than listed: the point of the sweep is to cover a document that
    does not exist yet, which is exactly what a list cannot do.

    :return: The documents.
    """
    return [
        SkillDocument.read_from(path)
        for path in sorted(
            (RepositoryLocation.PLUGIN / SkillDirectory.DIRECTORY).rglob("*.md")
        )
    ]


# %% the rule


def test_no_skill_document_offers_the_setup_instead_of_running_it() -> None:
    """
    A document that mentions the setup skill instructs running it, never offering it.
    """
    offenders = {
        document.relative_path: document.offer_instructions
        for document in skill_documents()
        if document.offer_instructions
    }
    assert offenders == {}


def test_the_sweep_reads_the_skill_documents_rather_than_nothing() -> None:
    """
    Guards the rule above against passing vacuously on a moved or renamed directory.

    Asserts only that documents were found, not which: skills are added and their
    documents move between them, and pinning the set here would make an unrelated change
    fail this module.
    """
    assert skill_documents() != []


# %% each skill gates on its own checks

COMMAND_SEPARATOR = " "
"""
Separates the words of a command line.
"""

GATE_COMMAND = RegularExpression.sequence(
    gate.__name__.removeprefix(f"{PackageLocation.DIRECTORY.name}."),
    COMMAND_SEPARATOR,
    GateOption.SKILL,
    COMMAND_SEPARATOR,
    CharacterSet.any_of(CharacterRange.ASCII_LOWERCASE_LETTER, "-")
    .one_or_more()
    .captured_as(GateGroup.SKILL),
).compiled()
"""
How a document runs a skill's setup gate, naming the skill.
"""


def gated_skill_names() -> list[str]:
    """
    :return: Every skill name a skill document runs the setup gate with, in the order
        found.
    """
    return [
        match[GateGroup.SKILL]
        for document in skill_documents()
        for match in GATE_COMMAND.finditer(document.text)
    ]


def gate_skill_names() -> set[str]:
    """
    :return: The name of every skill the gate knows.
    """
    return {skill.skill_name for skill in BasstlerSkill.every_skill()}


def test_every_skill_a_document_gates_is_a_gated_skill() -> None:
    """
    A document runs the gate only with a skill the gate knows.
    """
    assert set(gated_skill_names()) <= gate_skill_names()


def test_every_gated_skill_runs_its_gate() -> None:
    """
    Every skill the gate knows runs it from its own document.
    """
    assert gate_skill_names() <= set(gated_skill_names())
