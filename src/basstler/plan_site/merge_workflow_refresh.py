"""
Propose the current plan site merge workflow when the notes repository's default branch
holds an older one, and print the step left to the user.

Usage:
    "${BASSTLER_PYTHON}" -m basstler.plan_site.merge_workflow_refresh
"""

from __future__ import annotations

from cyclopts import App

from basstler.exit_codes import StackExitCode
from basstler.plan_site.build_start import recorded_site
from basstler.plan_site.publication import clone_publication
from basstler.standard_streams import StandardStreamHandler
from basstler.upstream_reviews.action.branch import BasstlerSource

logger = StandardStreamHandler.logger_for(__name__)
"""
This module's logger, which is also what its command prints through.
"""

app = App(help=__doc__)
"""
The command, which takes no arguments.
"""


@app.default
def refresh_merge_workflow() -> StackExitCode:
    """
    Print what is left to the user once the current merge workflow is proposed, and
    nothing when the default branch holds it or no merge workflow, or no plan site lists
    this repository.

    :return: :attr:`StackExitCode.SUCCESS`, also when a step is left: the line printed
        is the answer.
    """
    site = recorded_site()
    if site is None:
        return StackExitCode.SUCCESS
    step = clone_publication(
        BasstlerSource.LATEST_RELEASE.value, site.repository.full_name
    ).refresh_merge_workflow()
    if step is None:
        return StackExitCode.SUCCESS
    logger.info(
        "The plan site's merge workflow on the default branch is out of date, so a pull "
        "request changing its state may start no build and the site keeps showing the "
        f"old state. The current one is proposed:\n{step.render()}"
    )
    return StackExitCode.SUCCESS


if __name__ == "__main__":
    app()
