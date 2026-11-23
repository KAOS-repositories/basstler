"""
The files and directories the code rules name.
"""

from __future__ import annotations

from pathlib import Path

from basstler.locations import INSTALLED_PACKAGE, PathEnumeration, ShippedPath


class InstructionsTemplate(PathEnumeration):
    """
    The templates the agent instruction files are rendered from.
    """

    AGENTS = INSTALLED_PACKAGE.shipped(ShippedPath.TEMPLATES / "agents.md.jinja")
    """
    The content of ``AGENTS.md``: rules under the headings of their sections.
    """


class CodeRulesPackageLocation(PathEnumeration):
    """
    The files of the installed package the code rules read, as absolute paths.
    """

    GITHUB_REPOSITORY_MODULE = INSTALLED_PACKAGE.shipped(
        Path("github") / "repository.py"
    )
    """
    The module whose :class:`basstler.github.repository.Repository` builds every
    address within a repository.
    """


class CodeRulesProjectLocation(PathEnumeration):
    """
    The files the code rules write in a project, relative to its root.
    """

    AGENTS_INSTRUCTIONS = Path("AGENTS.md")
    """
    The instructions agents read, generated from :mod:`basstler.code_rules.rules`.
    """
