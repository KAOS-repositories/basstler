"""
The files and directories plans and their items name.
"""

from __future__ import annotations

from pathlib import Path

from basstler.locations import (
    INSTALLED_PACKAGE,
    PathEnumeration,
    PluginFile,
    PluginLocation,
    ProjectLocation,
    ShippedPath,
)


class PlanHandoverLocation(PathEnumeration):
    """
    The files a plan handover holds, relative to its directory.
    """

    GUIDE = Path("HANDOVER.md")
    """
    The instructions a coding agent continues the handed-over plans from without basstler.
    """

    PLANS = Path("plans")
    """
    One directory per plan, holding its documents as the notes branch does.
    """

    PULL_REQUEST_PROGRESS = Path("pr-progress")
    """
    The progress note of each handed-over item's branch, named after the branch.
    """

    REPOSITORY_RULES = Path("repository-rules.yaml")
    """
    The rules every plan of the repository follows, in the notes branch's format.
    """

    GUIDE_TEMPLATE = INSTALLED_PACKAGE.shipped(
        ShippedPath.TEMPLATES / "plan_handover_guide.md.jinja"
    )
    """
    The template :attr:`GUIDE` is rendered from.
    """

    TAKEN_OVER_TEMPLATE = INSTALLED_PACKAGE.shipped(
        ShippedPath.TEMPLATES / "plan_handover_taken_over.md.jinja"
    )
    """
    The template of the comment a handover pull request is closed with.
    """

    PULL_REQUEST_DIRECTORY = Path("plan-handover")
    """
    Where a handover pull request's commit holds the handover, relative to its root.
    """

    PULL_REQUEST_TEMPLATE = INSTALLED_PACKAGE.shipped(
        ShippedPath.TEMPLATES / "plan_handover_pull_request.md.jinja"
    )
    """
    The template a handover pull request's description is rendered from.
    """


class PlanPackageLocation(PathEnumeration):
    """
    The files the plan distribution ships, as absolute paths.
    """

    PLAN_ITEM_MODE_DEFAULTS = INSTALLED_PACKAGE.shipped(
        Path("plan") / "plan-item-modes.toml"
    )
    """
    The shipped plan-item execution modes.
    """


class PlanProjectLocation(PathEnumeration):
    """
    The files of plans and their items on the personal-notes branch, relative to its root.
    """

    PLAN_BRANCH_INDEX = ProjectLocation.PLANS / "_generated" / "branch-index.tsv"
    """
    The generated index naming the plan each item branch belongs to.

    Mirrors ``PLAN_BRANCH_INDEX_PATH`` in ``resolve-personal-notes-config.sh``.
    """

    PULL_REQUEST_PROGRESS = ProjectLocation.PERSONAL_NOTES / "pr-progress"
    """
    Where the personal-notes branch keeps each branch's progress note, named after the
    branch.

    Mirrors ``PR_PROGRESS_DIRECTORY`` in ``resolve-personal-notes-config.sh``.
    """

    PERSONAL_PLAN_ITEM_MODES = ProjectLocation.PERSONAL_NOTES / "plan-item-modes.toml"
    """
    The per-user override of :attr:`PlanPackageLocation.PLAN_ITEM_MODE_DEFAULTS`.
    """


class PlanPluginLocation(PluginFile):
    """
    The plugin's scripts plans are saved with, relative to the plugin's root.
    """

    PLAN_SAVING_SCRIPT = PluginLocation.HOOKS / "save-plan.sh"
    """
    Pushes an edited plan manifest and roadmap to the personal-notes branch.
    """
