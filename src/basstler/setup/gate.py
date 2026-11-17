"""
The setup gate a skill passes before its first step: check-setup.sh reports only the
checks that skill needs, so a row it does not use never stops it.

Usage:
    basstler.sh setup.gate --skill <skill>
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter

from basstler.class_name import HyphenatedClassName
from basstler.class_property import classproperty
from basstler.exit_codes import CommandFailure, ExitCode
from basstler.locations import ClaudeCodeVariable
from basstler.plugin_root import PluginRoot
from basstler.setup.exceptions import UnknownSkillError
from basstler.setup.report import (
    ReportRowField,
    SetupCheck,
    SetupCheckScript,
    SetupReport,
)
from basstler.standard_streams import StandardStreamHandler

logger = StandardStreamHandler.logger_for(__name__)
"""
This module's logger, which is also what its command prints through.
"""

# %% the skills that gate on their setup


class CheckSetupOption(StrEnum):
    """
    The check-setup.sh flags a gate passes.
    """

    ONLY = "--only"
    """
    Reports only the check named after it, and exits for the named checks alone.
    """

    REQUIRE_UPSTREAM = "--require-upstream"
    """
    Makes a project naming no upstream a check that needs setup.
    """


@dataclass(frozen=True)
class BasstlerSkill(HyphenatedClassName, ABC):
    """
    A skill that checks its setup before its first step.

    A subclass declares the checks it needs beyond the ones every skill needs, and the
    gate follows; :meth:`named` finds it among the direct subclasses.
    """

    @classproperty
    def skill_name(cls) -> str:
        """
        The name a session invokes the skill with: its class name, hyphenated.
        """
        return cls.hyphenated_class_name()

    @classproperty
    @abstractmethod
    def additional_checks(cls) -> frozenset[SetupCheck]:
        """
        The checks this skill needs beyond :attr:`shared_checks`.
        """

    @classproperty
    def shared_checks(cls) -> frozenset[SetupCheck]:
        """
        What every gated skill needs: the plugin, the session start it registers, the
        package its commands run at the plugin's own release, and the notes branch.
        """
        return frozenset(
            {
                SetupCheck.TOOLING_FILES,
                SetupCheck.SESSION_START_HOOK,
                SetupCheck.CLAUDE_LOCAL_MD_IGNORED,
                SetupCheck.PACKAGE_DEPENDENCIES,
                SetupCheck.BASSTLER_VERSION,
                SetupCheck.CLAUDE_LOCAL_MD,
                SetupCheck.NOTES_REPOSITORY_ACCESS,
                SetupCheck.NOTES_BRANCH,
            }
        )

    @classproperty
    def required_checks(cls) -> frozenset[SetupCheck]:
        """
        The checks this skill's steps depend on; no other row stops it.
        """
        return cls.shared_checks | cls.additional_checks

    @classmethod
    def check_setup_arguments(cls) -> list[str]:
        """
        :return: The flags that make check-setup.sh report exactly :attr:`required_checks`,
            requiring an upstream when :attr:`SetupCheck.STACK_UPSTREAM` is among them.
        """
        upstream = (
            [CheckSetupOption.REQUIRE_UPSTREAM]
            if SetupCheck.STACK_UPSTREAM in cls.required_checks
            else []
        )
        return [
            *upstream,
            *(
                argument
                for check in SetupCheck
                if check in cls.required_checks
                for argument in (CheckSetupOption.ONLY, check)
            ),
        ]

    @classmethod
    def gate(cls, script: SetupCheckScript) -> SetupReport:
        """
        :param script: The clone's check-setup.sh.
        :return: What it reports for this skill's checks, exiting for them alone.
        :raises CheckSetupFailedError: If it exits with a status that carries no report,
            or its report lacks one of those checks or holds an unreadable row.
        """
        return SetupReport.from_completed_process(
            script.run(*cls.check_setup_arguments()), cls.required_checks
        )

    @classmethod
    def every_skill(cls) -> tuple[type[BasstlerSkill], ...]:
        """
        :return: Every gated skill, in the order they are defined.
        """
        return tuple(
            skill for family in cls.__subclasses__() for skill in family.leaves()
        )

    @classmethod
    def leaves(cls) -> tuple[type[BasstlerSkill], ...]:
        """
        :return: This class when no skill subclasses it, else the skills that do.
        """
        subclasses = cls.__subclasses__()
        if not subclasses:
            return (cls,)
        return tuple(skill for subclass in subclasses for skill in subclass.leaves())

    @classmethod
    def named(cls, skill_name: str) -> type[BasstlerSkill]:
        """
        :param skill_name: A name a session invokes a skill with.
        :return: The gated skill of that name.
        :raises UnknownSkillError: If no gated skill has that name.
        """
        for skill in BasstlerSkill.every_skill():
            if skill.skill_name == skill_name:
                return skill
        raise UnknownSkillError(
            skill_name, [skill.skill_name for skill in BasstlerSkill.every_skill()]
        )


class PlanSavingSkill(BasstlerSkill, ABC):
    """
    A skill that saves a plan, so it needs the notes file, a session that can start the
    plan site's build, and the identity its commits carry.
    """

    @classproperty
    def additional_checks(cls) -> frozenset[SetupCheck]:
        return frozenset(
            {
                SetupCheck.NOTES_FILE,
                SetupCheck.PLAN_SITE_ACCESS,
                SetupCheck.GIT_IDENTITY,
            }
        )


class PlanCreate(PlanSavingSkill):
    """
    Creates a plan on the personal-notes branch.
    """


class AddPlanItem(PlanSavingSkill):
    """
    Decides where new work belongs and adds it to a plan.
    """


class PlanItemKickoff(PlanSavingSkill):
    """
    Starts a plan item.
    """


class PlanItemResolve(PlanSavingSkill):
    """
    Unblocks or resumes a plan item already underway.
    """


class UpstreamReviews(BasstlerSkill):
    """
    Reports a fork branch's upstream pull request.
    """

    @classproperty
    def additional_checks(cls) -> frozenset[SetupCheck]:
        return frozenset(
            {SetupCheck.STACK_UPSTREAM, SetupCheck.UPSTREAM_REVIEWS_ACTION}
        )


# %% the command line


class GateOption(StrEnum):
    """
    The options the command takes.
    """

    SKILL = "--skill"
    """
    The skill about to start.
    """


gate_app = App(help=__doc__)
"""
The command, which takes the skill about to start.
"""


@gate_app.default
def check_skill_setup(
    *, skill: Annotated[str, Parameter(name=GateOption.SKILL)]
) -> ExitCode:
    """
    Print check-setup.sh's rows for the checks a skill needs, and exit as it does.

    :param skill: The name of the skill about to start.
    :return: check-setup.sh's status for that skill's checks.
    :raises UnknownSkillError: If no gated skill has that name.
    """
    project_root = Path(
        os.environ.get(ClaudeCodeVariable.PROJECT_DIRECTORY, Path.cwd())
    )
    report = BasstlerSkill.named(skill).gate(
        SetupCheckScript(project_root, os.environ, PluginRoot.locate(os.environ))
    )
    for check, result in report.results.items():
        logger.info(f"{check}{ReportRowField.SEPARATOR}{result.fields}")
    return report.exit_code


def main() -> ExitCode:
    """
    Run the gate, ending with the status a refusal carries.

    :return: The process exit code.
    """
    try:
        return gate_app(result_action="return_value")
    except CommandFailure as failure:
        logger.error(f"{failure}")
        return failure.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
