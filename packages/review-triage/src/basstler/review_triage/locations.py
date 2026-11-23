"""
The files and directories the review triage names.
"""

from __future__ import annotations

from pathlib import Path

from basstler.locations import (
    INSTALLED_PACKAGE,
    PathEnumeration,
    RepositoryStateLocation,
    ShippedPath,
    WorkflowLocation,
)


class ReviewTriageLocation(PathEnumeration):
    """
    The files the review triage reads beside its modules.
    """

    MARK_FILE_AS_VIEWED = INSTALLED_PACKAGE.shipped(
        Path("review_triage") / "mark_file_as_viewed.graphql"
    )
    """
    The GraphQL mutation marking one file of a pull request viewed.
    """

    REPORT_TEMPLATE = INSTALLED_PACKAGE.shipped(
        ShippedPath.TEMPLATES / "review_triage_report.md.jinja"
    )
    """
    The Markdown report of which files of a pull request need review.
    """

    PULL_REQUEST_FILES = INSTALLED_PACKAGE.shipped(
        Path("review_triage") / "pull_request_files.graphql"
    )
    """
    The GraphQL query reading one page of the files GitHub lists in a pull request,
    with its head commit.
    """

    MARK_VIEWED_SETUP_TEMPLATE = INSTALLED_PACKAGE.shipped(
        ShippedPath.TEMPLATES / "review_triage_mark_viewed_setup.md.jinja"
    )
    """
    The report of setting a repository's Actions up to mark files viewed.
    """

    MARK_VIEWED_CALLER_TEMPLATE = INSTALLED_PACKAGE.shipped(
        ShippedPath.TEMPLATES / "review_triage_mark_viewed_caller.yml"
    )
    """
    The workflow installed on a user's repository that calls basstler's reusable
    workflow marking files viewed.
    """


class ReviewTriageStateLocation(PathEnumeration):
    """
    The review triage's scratch state, relative to a repository's common git directory.
    """

    VIEWED_MARKING_STAMP = RepositoryStateLocation.DIRECTORY / "viewed-marked-head"
    """
    The pull request the files were last marked viewed on, and the head commit they
    were marked at.
    """


class ReviewTriageWorkflowLocation(PathEnumeration):
    """
    The GitHub Actions workflows that mark a pull request's files viewed, relative to the root of the branch that holds each.
    """

    REVIEW_TRIAGE_MARK_VIEWED = (
        WorkflowLocation.DIRECTORY / "review-triage-mark-viewed.yml"
    )
    """
    basstler's reusable workflow that marks a pull request's mechanical files viewed.
    """


class ReviewTriageRepositoryLocation(PathEnumeration):
    """
    The files of basstler's own repository the review triage names, relative to its root.
    """

    REVIEW_TRIAGE_README = Path("docs") / "review-triage" / "README.md"
    """
    How to use the review triage and set up marking files viewed.
    """
