"""
The code rules a project is held to, as rulesets its playbook holds.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from basstler.code_rules.checker import CodeRuleChecker
from basstler.code_rules.fixes import FixableChecker
from basstler.code_rules.rule import Section
from basstler.code_rules.rule_module import RuleModule
from basstler.playbook.playbook import PlaybookFile
from basstler.playbook.ruleset import Ruleset


@dataclass(frozen=True)
class CodeRuleset(Ruleset[type[Section]]):
    """
    The top-level sections of ``AGENTS.md`` one rule module declares.
    """

    rule_module: RuleModule
    """
    The module, or package of modules, declaring the sections.
    """

    @property
    def rules(self) -> tuple[type[Section], ...]:
        return tuple(self.rule_module.sections)


@dataclass(frozen=True)
class ProjectCodeRules:
    """
    Every code ruleset in a project's playbook.
    """

    rulesets: tuple[CodeRuleset, ...]
    """
    The rulesets, in playbook order.
    """

    @classmethod
    def of_project(cls, project_root: Path) -> ProjectCodeRules:
        """
        :param project_root: The project's root.
        :return: The code rulesets of the playbook the project runs basstler with.
        """
        return cls(PlaybookFile(project_root).read().components_of(CodeRuleset))

    @property
    def sections(self) -> list[type[Section]]:
        """
        The top-level sections of every ruleset, each ruleset's in its own order.
        """
        return [section for ruleset in self.rulesets for section in ruleset.rules]

    @property
    def checkers(self) -> tuple[CodeRuleChecker, ...]:
        """
        The checker of every rule in every ruleset.
        """
        return tuple(
            checker
            for ruleset in self.rulesets
            for checker in ruleset.rule_module.checkers
        )

    @property
    def fixable_checkers(self) -> tuple[FixableChecker, ...]:
        """
        The checkers among :attr:`checkers` whose rule has a fix.
        """
        return tuple(
            checker
            for ruleset in self.rulesets
            for checker in ruleset.rule_module.fixable_checkers
        )
