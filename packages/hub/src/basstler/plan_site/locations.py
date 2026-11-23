"""
The files and directories the plan site names.
"""

from __future__ import annotations

from basstler.locations import (
    INSTALLED_PACKAGE,
    PathEnumeration,
    ProjectLocation,
    ShippedPath,
    WorkflowLocation,
)


class SiteTemplate(PathEnumeration):
    """
    The templates the plan site's pages and stylesheet are rendered from.
    """

    STYLESHEET = INSTALLED_PACKAGE.shipped(ShippedPath.TEMPLATES / "site.css")
    """
    The one stylesheet every page of the site links.
    """

    LAYOUT = INSTALLED_PACKAGE.shipped(ShippedPath.TEMPLATES / "site_layout.html")
    """
    The document every page of the site fills in.
    """

    PARTS = INSTALLED_PACKAGE.shipped(ShippedPath.TEMPLATES / "site_parts.html")
    """
    The markup the site's pages share: progress cards, the health banner, dependency
    chips and action buttons.
    """

    HUB = INSTALLED_PACKAGE.shipped(ShippedPath.TEMPLATES / "hub.html")
    """
    The hub: a card per repository.
    """

    REPOSITORY_INDEX = INSTALLED_PACKAGE.shipped(
        ShippedPath.TEMPLATES / "site_index.html"
    )
    """
    One repository's index: a card per plan.
    """

    PLAN = INSTALLED_PACKAGE.shipped(ShippedPath.TEMPLATES / "site_plan.html")
    """
    One plan's page: a column per wave, a card per item.
    """

    PLAN_SCRIPT = INSTALLED_PACKAGE.shipped(ShippedPath.TEMPLATES / "site_plan.js")
    """
    A plan page's behaviour: copying commands, choosing a model, revealing an item.
    """

    LIVE_STATE_SCRIPT = INSTALLED_PACKAGE.shipped(
        ShippedPath.TEMPLATES / "site_live_state.js"
    )
    """
    The script every site page reads a pull request's live state from GitHub's answer
    with, and re-checks with when the tab is shown again.
    """

    LIVE_PROGRESS_SCRIPT = INSTALLED_PACKAGE.shipped(
        ShippedPath.TEMPLATES / "site_live_progress.js"
    )
    """
    The hub's and repository indexes' script that recounts every progress card from
    each repository's pull request listing.
    """

    PLAN_PULL_REQUEST_RECHECK_SCRIPT = INSTALLED_PACKAGE.shipped(
        ShippedPath.TEMPLATES / "site_plan_pull_request_recheck.js"
    )
    """
    The plan page's script that reads every pull request's state from GitHub in the
    browser, and shows when the page was last refreshed.
    """


class SiteWorkflowLocation(PathEnumeration):
    """
    The GitHub Actions workflows that build the plan site, relative to the root of the branch that holds each.
    """

    PLAN_SITE_BUILD = WorkflowLocation.DIRECTORY / "plan-site-build.yml"
    """
    basstler's reusable workflow that builds and deploys the plan site.
    """

    PLAN_SITE_DISPATCH = WorkflowLocation.DIRECTORY / "plan-site-dispatch.yml"
    """
    The workflow on a notes branch that starts :attr:`~basstler.locations.WorkflowLocation.PLAN_SITE` on every push to it.
    """

    PLAN_SITE_MERGE = WorkflowLocation.DIRECTORY / "plan-site-merge.yml"
    """
    The workflow on a notes repository's default branch that starts :attr:`~basstler.locations.WorkflowLocation.PLAN_SITE`
    whenever a pull request merges.
    """


class SiteProjectLocation(PathEnumeration):
    """
    The plan site's files on the personal-notes branch, relative to its root.
    """

    PLAN_HUB = ProjectLocation.PLANS / "_hub.yaml"
    """
    The plan hub file: the site's address and every repository it publishes.

    Mirrors ``PLAN_HUB_PATH`` in ``resolve-personal-notes-config.sh``.
    """
