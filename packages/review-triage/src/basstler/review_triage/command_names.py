"""
The names of the ``basstler review-triage`` commands.
"""

from __future__ import annotations


from basstler.basstler_command import BasstlerCommand
from basstler.class_property import classproperty

# %% the commands


class ReviewTriageCommand(BasstlerCommand):
    """
    The ``basstler review-triage`` command group and its commands, by name.
    """

    @classproperty
    def group(cls) -> str:
        return "review-triage"

    REPORT = "report"
    """
    Print which files of a pull request need review, as Markdown.
    """
    MARK_VIEWED = "mark-viewed"
    """
    Mark a pull request's mechanical files viewed for the logged-in account.
    """
    DECLARE = "declare"
    """
    Print the description comment declaring renames.
    """
    REQUEST_MARK_VIEWED = "request-mark-viewed"
    """
    Ask a repository's Actions to mark a pull request's mechanical files viewed.
    """
    MARK_VIEWED_IN_REVIEWS = "mark-viewed-in-reviews"
    """
    Mark the mechanical files of every open pull request the logged-in account reviews
    viewed, each from where it last viewed it.
    """
    SET_UP_MARK_VIEWED = "set-up-mark-viewed"
    """
    Set a repository's Actions up to mark files viewed, listing the steps left.
    """
    SPLIT_MECHANICAL = "split-mechanical"
    """
    Replace a pull request's commits with one making its mechanical changes and one
    making every other change.
    """
