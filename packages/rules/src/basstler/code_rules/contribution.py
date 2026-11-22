"""
What basstler-rules adds to the default playbook.
"""

from __future__ import annotations

from basstler.class_property import classproperty
from basstler.code_rules import rules
from basstler.code_rules.command_line import code_rules_app
from basstler.code_rules.rule_module import RuleModule
from basstler.code_rules.ruleset import CodeRuleset
from basstler.playbook.command_group import CommandGroup
from basstler.playbook.component import PlaybookComponent
from basstler.playbook.contribution import PackageContribution


class RulesContribution(PackageContribution):
    """
    The ``basstler code-rules`` commands and basstler's own code rules.
    """

    @classproperty
    def components(cls) -> tuple[PlaybookComponent, ...]:
        return (CommandGroup(code_rules_app), CodeRuleset(RuleModule(rules)))
