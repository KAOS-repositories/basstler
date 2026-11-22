"""
Tests for the workflow that publishes a release's distributions to PyPI: that it follows
a finished release and publishes through trusted publishing alone.
"""

from __future__ import annotations

from enum import StrEnum

import pytest
import yaml
from basstler.github.workflows import ActivityType
from basstler.packaging.package_index import PackageIndex
from basstler.packaging.publish_workflow import (
    IdentityTokenPermission,
    PublishAction,
    PublishActionInput,
    PublishWorkflow,
)
from basstler.text_file import TextFile

from basstler_testing.constants.paths import RepositoryLocation

# %% the workflow


class PublishJobName(StrEnum):
    """
    The jobs of this repository's publish workflow.
    """

    BUILD = "build"
    PUBLISH = "publish-pypi"


@pytest.fixture(scope="module")
def workflow() -> PublishWorkflow:
    """
    The publish workflow file, parsed.
    """
    return PublishWorkflow.read(RepositoryLocation.PUBLISH_WORKFLOW)


RELEASE_WORKFLOW_NAME = yaml.safe_load(
    TextFile(RepositoryLocation.RELEASE_WORKFLOW).read()
)["name"]
"""
The name the Release workflow declares, which the publish workflow waits for.
"""

# %% when it runs


def test_the_workflow_follows_a_finished_release(workflow: PublishWorkflow):
    """
    It starts when the Release workflow completes, so a commit that was not released
    publishes nothing.
    """
    trigger = workflow.triggers.followed_run

    assert trigger.workflow_names == [RELEASE_WORKFLOW_NAME]
    assert trigger.trigger_types == [ActivityType.COMPLETED]


def test_a_release_that_failed_publishes_nothing(workflow: PublishWorkflow):
    """
    A Release run that failed tagged nothing, so there is nothing to publish.
    """
    assert "github.event.workflow_run.conclusion == 'success'" in (
        workflow.jobs[PublishJobName.BUILD].condition
    )


def test_a_tag_can_be_published_by_hand(workflow: PublishWorkflow):
    """
    A release whose publishing stopped is finished by naming its tag, since the next
    release run finds nothing new to tag.
    """
    assert "tag" in workflow.triggers.manual.inputs_by_name


# %% what is built


def test_every_distribution_is_built_from_the_tagged_commit_with_its_history(
    workflow: PublishWorkflow,
):
    """
    The version is read from the tag, which a shallow checkout does not have.
    """
    checkout = workflow.jobs[PublishJobName.BUILD].steps[0]

    assert checkout.action_inputs_by_name["fetch-depth"] == 0


def test_the_build_covers_every_member_of_the_workspace(workflow: PublishWorkflow):
    """
    One build produces every distribution, so none is left at the previous release.
    """
    build = workflow.jobs[PublishJobName.BUILD]

    assert any("uv build --all-packages" in (step.run or "") for step in build.steps)


# %% how it publishes


def test_the_workflow_holds_no_credential(workflow: PublishWorkflow):
    """
    Trusted publishing is the only way in: no secret and no token appears in the file.
    """
    publish = workflow.jobs[PublishJobName.PUBLISH].step_using(PublishAction.PUBLISH)

    assert "secrets." not in TextFile(RepositoryLocation.PUBLISH_WORKFLOW).read()
    assert PublishActionInput.PASSWORD not in publish.action_inputs_by_name


def test_only_the_job_that_publishes_may_request_an_identity_token(
    workflow: PublishWorkflow,
):
    """
    The identity token is what proves to the index which workflow publishes, so no other
    job can ask for one.
    """
    granting = {
        name for name, job in workflow.jobs.items() if job.requests_identity_token
    }

    assert granting == {PublishJobName.PUBLISH}
    assert IdentityTokenPermission.SCOPE not in workflow.permissions


def test_the_job_publishes_from_the_environment_of_pypi(workflow: PublishWorkflow):
    """
    The index's trusted publisher names the environment.
    """
    assert workflow.jobs[PublishJobName.PUBLISH].environment == PackageIndex.PYPI


def test_pypi_is_published_to_at_its_default_address(workflow: PublishWorkflow):
    """
    The publish action's default address is PyPI itself, so none is named.
    """
    publish = workflow.jobs[PublishJobName.PUBLISH].step_using(PublishAction.PUBLISH)

    assert (
        publish.action_inputs_by_name.get(PublishActionInput.REPOSITORY_URL)
        == PackageIndex.PYPI.upload_url
    )


def test_publishing_waits_for_the_build_and_takes_its_files(workflow: PublishWorkflow):
    """
    What PyPI gets is what the build uploaded, not a second build.
    """
    publish = workflow.jobs[PublishJobName.PUBLISH]

    assert publish.needs == [PublishJobName.BUILD]
    assert PublishAction.DOWNLOAD in {step.action for step in publish.steps}
    assert PublishAction.UPLOAD in {
        step.action for step in workflow.jobs[PublishJobName.BUILD].steps
    }


def test_a_publish_that_stopped_can_be_run_again(workflow: PublishWorkflow):
    """
    Files an index already holds are skipped, so running a half-published release again
    uploads what is missing instead of failing on what is there.
    """
    publish = workflow.jobs[PublishJobName.PUBLISH].step_using(PublishAction.PUBLISH)

    assert publish.action_inputs_by_name[PublishActionInput.SKIP_EXISTING] is True
