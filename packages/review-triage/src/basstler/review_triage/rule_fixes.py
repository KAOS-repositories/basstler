"""
Proving a Python file's change mechanical by recomputing the fixes of the code rules on
its base version.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

import libcst

from basstler.code_modification.positions import PositionedModule
from basstler.code_rules import rules
from basstler.code_rules.fixes import SourceFixer
from basstler.code_rules.rule import Section
from basstler.code_rules.rule_module import RuleModule
from basstler.git.commit_range import FileVersions
from basstler.review_triage.comparison import (
    ChangeKind,
    ChangeKinds,
    FileJudgment,
    JudgmentContext,
    PythonComparison,
)
from basstler.review_triage.definition_moves import DefinitionMoveComparison

# %% what a rule's fix changes

FIXABLE_RULES = RuleModule(rules).fixable_rules
"""
Every code rule whose checker has a fix.
"""

RuleFixChange = ChangeKind(
    "RuleFixChange",
    [(rule.name, rule.name.lower().replace("_", " ")) for rule in FIXABLE_RULES],
    module=__name__,
)
"""
The change the fix of each rule in :data:`FIXABLE_RULES` makes, a member named after the
rule.
"""

# %% the judgment


@dataclass(frozen=True)
class RuleFixComparison(FileJudgment):
    """
    Judges a file as :attr:`comparison` does, and a Python file it cannot prove
    mechanical by comparing the head with the base once the fixes of the rules the base
    breaks and the head no longer does are recomputed on the base.
    """

    comparison: FileJudgment = field(default_factory=DefinitionMoveComparison)
    """
    How a file is compared, before and after the fixes are recomputed.
    """

    fixable_rules: tuple[Section, ...] = FIXABLE_RULES
    """
    The rules whose fixes are recomputed.
    """

    def applies_to(self, change: FileVersions) -> bool:
        return self.comparison.applies_to(change)

    def changes(
        self, change: FileVersions, context: JudgmentContext
    ) -> ChangeKinds | None:
        kinds = self.comparison.changes(change, context)
        if (
            kinds is not None
            or change.base_text is None
            or change.head_text is None
            or change.path.suffix not in PythonComparison.suffixes
        ):
            return kinds
        path = Path(change.path)
        base = libcst.parse_module(change.base_text)
        fixed_rules = self.broken_rules(base, path) - self.broken_rules(
            libcst.parse_module(change.head_text), path
        )
        if not fixed_rules:
            return None
        fixer = SourceFixer(
            tuple(rule.checker for rule in self.fixable_rules if rule in fixed_rules)
        )
        fixed = fixer.fix_module(base, path).result.code
        fixed_kinds = self.comparison.changes(replace(change, base_text=fixed), context)
        if fixed_kinds is None:
            return None
        return fixed_kinds | {RuleFixChange[rule.name] for rule in fixed_rules}

    def broken_rules(self, module: libcst.Module, path: Path) -> frozenset[Section]:
        """
        :param module: A version of the file at *path*.
        :return: The rules among :attr:`fixable_rules` that *module* breaks somewhere.
        """
        positioned = PositionedModule(module)
        return frozenset(
            rule
            for rule in self.fixable_rules
            if rule.checker.checks(path)
            and next(rule.checker.specifications_of_module(positioned), None)
            is not None
        )
