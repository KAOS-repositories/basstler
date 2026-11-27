"""
The ``basstler code-rules`` commands: checking code against the rules, fixing it, and
generating ``AGENTS.md`` from them.
"""

from __future__ import annotations

from pathlib import Path

from cyclopts import App

from basstler.code_modification.source_file import EditablePythonSourceFile
from basstler.code_rules.checker import CodeRulesCheck, StagedLines
from basstler.code_rules.commands import CodeRulesCommand
from basstler.code_rules.fixes import SourceFixer
from basstler.code_rules.instructions import AgentsInstructions
from basstler.code_rules.package_boundaries import (
    PackageAtCommit,
    PackageBoundaryChecker,
)
from basstler.code_rules.ruleset import ProjectCodeRules
from basstler.exit_codes import ExitCode
from basstler.git.commands import GitCommandRunner
from basstler.code_rules.locations import CodeRulesProjectLocation
from basstler.standard_streams import StandardStreamHandler

logger = StandardStreamHandler.logger_for(__name__)
"""
This module's logger, which is also what its commands print through.
"""


class CodeRulesExitCode(ExitCode):
    """
    What a ``basstler code-rules`` command's exit status tells pre-commit.
    """

    SUCCESS = 0
    """
    Nothing had to change.
    """

    CHANGES_NEEDED = 1
    """
    Code breaks a rule, a boundary crossing is new, or ``AGENTS.md`` was rewritten or
    is out of date.
    """


code_rules_app = App(
    name=CodeRulesCommand.group,
    help=(
        "Check code against the repository's rules, fix it, and generate AGENTS.md "
        "from them."
    ),
)
"""
The ``code-rules`` command group.
"""


@code_rules_app.command(name=CodeRulesCommand.CHECK)
def check(
    paths: list[Path] | None = None, *, all_lines: bool = False
) -> CodeRulesExitCode:
    """
    Report the code in *paths* that breaks a rule a checker enforces.

    :param paths: The Python files to check.
    :param all_lines: Check every line, not only those the staged change touches.
    """
    code_rules_check = CodeRulesCheck(
        ProjectCodeRules.of_project(Path.cwd()).checkers,
        None if all_lines else StagedLines(GitCommandRunner(Path.cwd())),
    )
    violations = code_rules_check.violations(paths or [])
    for violation in violations:
        logger.error(violation.render())
    if violations:
        return CodeRulesExitCode.CHANGES_NEEDED
    return CodeRulesExitCode.SUCCESS


@code_rules_app.command(name=CodeRulesCommand.FIX)
def fix(paths: list[Path] | None = None) -> CodeRulesExitCode:
    """
    Rewrite each file in *paths* that breaks a rule with a fix, applying the fix to
    every place that breaks it; a file is written only once every file is fixed.

    :param paths: The Python files to fix.
    """
    fixer = SourceFixer(ProjectCodeRules.of_project(Path.cwd()).fixable_checkers)
    fixed_sources = {
        source_file: fixer.fix_module(source_file).result.code
        for source_file in map(EditablePythonSourceFile, paths or [])
    }
    changed = {
        source_file: source
        for source_file, source in fixed_sources.items()
        if source != source_file.read()
    }
    for source_file, source in changed.items():
        source_file.write(source)
        logger.info("Fixed %s", source_file.path)
    if changed:
        return CodeRulesExitCode.CHANGES_NEEDED
    return CodeRulesExitCode.SUCCESS


@code_rules_app.command(name=CodeRulesCommand.NEW_CROSSINGS)
def report_new_crossings(base_commit: str) -> CodeRulesExitCode:
    """
    Report each boundary crossing of the package that *base_commit* does not have.

    The base is read under the package map its own distributions declare, so a
    crossing only a change of a distribution's metadata creates is new as well; a module
    moved since keeps the base's crossings.

    :param base_commit: The commit the checked out package is compared with.
    """
    git = GitCommandRunner(Path.cwd())
    checker = PackageBoundaryChecker()
    with PackageAtCommit(git, base_commit, checker.workspace.root) as base_checker:
        if base_checker is None:
            logger.info(
                "%s holds no workspace of distributions, so nothing is compared",
                base_commit,
            )
            return CodeRulesExitCode.SUCCESS
        base_crossings = base_checker.package_crossings()
    renames = checker.module_renames(git, base_commit)
    added = checker.package_crossings().added_since(base_crossings.renamed(renames))
    for crossing in added:
        logger.error(crossing.new_import_message())
    if added:
        return CodeRulesExitCode.CHANGES_NEEDED
    return CodeRulesExitCode.SUCCESS


@code_rules_app.command(name=CodeRulesCommand.AGENTS_MD)
def generate_agents_instructions(*, verify: bool = False) -> CodeRulesExitCode:
    """
    Write the current directory's ``AGENTS.md`` from the rules.

    :param verify: Only report whether the file is current, writing nothing.
    """
    instructions = AgentsInstructions.of_repository(Path.cwd())
    if instructions.is_current():
        return CodeRulesExitCode.SUCCESS
    if verify:
        logger.error(
            "%s is out of date; run `%s`.",
            CodeRulesProjectLocation.AGENTS_INSTRUCTIONS,
            CodeRulesCommand.AGENTS_MD.invocation,
        )
        return CodeRulesExitCode.CHANGES_NEEDED
    instructions.write()
    logger.info("Wrote %s", CodeRulesProjectLocation.AGENTS_INSTRUCTIONS)
    return CodeRulesExitCode.CHANGES_NEEDED
