"""
The renames a pull request declares or rejects, in its description or on the command
line.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import yaml
from pydantic import Field

from basstler.class_property import classproperty
from basstler.github.pull_request_changes import PullRequestChanges
from basstler.json_model import ValidatedJSONModel
from basstler.review_triage.rename_sources import RenameSource
from basstler.review_triage.renames import Rename, RenameDecisions

# %% the declaration


class TriageDeclaration(ValidatedJSONModel):
    """
    What a pull request states about its renames, as YAML inside an HTML comment of its
    description that opens with :attr:`marker`.
    """

    renames: dict[str, str] = Field(default_factory=dict)
    """
    The new identifier of each old identifier the pull request renames throughout.
    """

    rejected_renames: tuple[str, ...] = ()
    """
    Old identifiers whose detected rename is not a rename.
    """

    @classproperty
    def marker(cls) -> str:
        """
        The word opening the HTML comment that holds a description's declaration.
        """
        return "review-triage"

    @classproperty
    def rename_separator(cls) -> str:
        """
        What separates the old identifier from the new one in a rename argument.
        """
        return "="

    @classmethod
    def from_description(cls, description: str) -> TriageDeclaration:
        """
        :param description: A pull request's description.
        :return: Its declaration, empty when it holds no declaration comment.
        :raises yaml.YAMLError: If the comment does not hold YAML.
        :raises pydantic.ValidationError: If the YAML does not have the model's shape.
        """
        match = re.search(
            rf"<!--\s*{re.escape(cls.marker)}\s*\n(.*?)-->", description, re.DOTALL
        )
        if match is None:
            return cls()
        return cls.from_json(yaml.safe_load(match.group(1)) or {})

    @classmethod
    def from_arguments(
        cls, renames: tuple[str, ...], rejected_renames: tuple[str, ...]
    ) -> TriageDeclaration:
        """
        :param renames: Each rename as ``old=new``.
        :param rejected_renames: The old identifiers whose rename is rejected.
        :return: The declaration the arguments make.
        :raises ValueError: If a rename lacks the separator.
        """
        pairs = (rename.split(cls.rename_separator, 1) for rename in renames)
        return cls(dict(pairs), rejected_renames)

    def comment(self) -> str:
        """
        :return: The comment declaring this, to paste into a pull request's
            description.
        """
        document = yaml.safe_dump(self.to_json(), sort_keys=False)
        return f"<!-- {self.marker}\n{document}-->"

    def decisions(self, found_by: RenameSource) -> RenameDecisions:
        """
        :param found_by: The source this declaration came through.
        :return: The renames it declares and the ones it rejects.
        """
        return RenameDecisions(
            tuple(Rename(old, new, found_by) for old, new in self.renames.items()),
            frozenset(self.rejected_renames),
        )


# %% the rename sources


@dataclass(frozen=True)
class DescriptionDeclaration(RenameSource):
    """
    Takes the renames the pull request's description declares and rejects.
    """

    @classproperty
    def label(cls) -> str:
        return "description"

    def decisions(self, changes: PullRequestChanges) -> RenameDecisions:
        return TriageDeclaration.from_description(
            changes.pull_request.description
        ).decisions(self)


@dataclass(frozen=True)
class ArgumentDeclaration(RenameSource):
    """
    Takes the renames given on the command line.
    """

    declaration: TriageDeclaration
    """
    The renames given and rejected.
    """

    @classproperty
    def label(cls) -> str:
        return "arguments"

    def decisions(self, changes: PullRequestChanges) -> RenameDecisions:
        return self.declaration.decisions(self)
