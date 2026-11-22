"""
Tests for the workflow that publishes a release's distributions to PyPI: that it follows
a finished release, publishes through trusted publishing alone, and reaches PyPI only
after TestPyPI took the same files.
"""

from __future__ import annotations

import pytest
import yaml

from basstler_testing.constants.paths import RepositoryLocation
from basstler_testing.publish_workflow_definition import (
    IdentityTokenPermission,
    PackageIndex,
    PublishAction,
    PublishJobName,
    PublishWorkflow,
)

# %% the workflow


@pytest.fixture(scope="module")
def workflow() -> PublishWorkflow:
    """
    The publish workflow file, parsed.
    """
    return PublishWorkflow.read()


RELEASE_WORKFLOW_NAME = yaml.safe_load(
    RepositoryLocation.RELEASE_WORKFLOW.read_text(encoding="utf-8")
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
    trigger = workflow.triggers.release_run

    assert trigger.workflows == [RELEASE_WORKFLOW_NAME]
    assert trigger.types == ["completed"]


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
    assert "tag" in workflow.triggers.manual.inputs


# %% what is built


def test_every_distribution_is_built_from_the_tagged_commit_with_its_history(
    workflow: PublishWorkflow,
):
    """
    The version is read from the tag, which a shallow checkout does not have.
    """
    checkout = workflow.jobs[PublishJobName.BUILD].steps[0]

    assert checkout.inputs["fetch-depth"] == 0


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
    assert "secrets." not in workflow.source
    for index in PackageIndex:
        step = workflow.publishing_to(index).step_using(PublishAction.PUBLISH)
        assert "password" not in step.inputs


def test_only_the_jobs_that_publish_may_request_an_identity_token(
    workflow: PublishWorkflow,
):
    """
    The identity token is what proves to the index which workflow publishes, so no other
    job can ask for one.
    """
    granting = {
        name for name, job in workflow.jobs.items() if job.requests_identity_token
    }

    assert granting == {index.job for index in PackageIndex}
    assert IdentityTokenPermission.SCOPE not in workflow.permissions


def test_each_index_is_published_from_an_environment_of_its_own(
    workflow: PublishWorkflow,
):
    """
    The index's trusted publisher names the environment, so one index's publisher cannot
    publish to the other.
    """
    for index in PackageIndex:
        assert workflow.publishing_to(index).environment == index


def test_each_index_is_published_to_at_its_own_address(workflow: PublishWorkflow):
    """
    The default address of the publish action is PyPI itself, so only TestPyPI names one.
    """
    for index in PackageIndex:
        step = workflow.publishing_to(index).step_using(PublishAction.PUBLISH)
        assert step.inputs.get("repository-url") == index.upload_url


def test_pypi_is_reached_only_after_testpypi_took_the_files(workflow: PublishWorkflow):
    """
    A release the test index refuses never reaches PyPI.
    """
    assert (
        PublishJobName.PUBLISH_TESTPYPI
        in workflow.publishing_to(PackageIndex.PYPI).needs
    )
    assert PublishJobName.BUILD in workflow.publishing_to(PackageIndex.TESTPYPI).needs


def test_both_indexes_publish_the_files_the_build_made(workflow: PublishWorkflow):
    """
    What TestPyPI took is byte for byte what PyPI gets, since both download the
    build's artifact instead of building again.
    """
    for index in PackageIndex:
        actions = {step.action for step in workflow.publishing_to(index).steps}
        assert PublishAction.DOWNLOAD in actions
    assert PublishAction.UPLOAD in {
        step.action for step in workflow.jobs[PublishJobName.BUILD].steps
    }


def test_a_publish_that_stopped_can_be_run_again(workflow: PublishWorkflow):
    """
    Files an index already holds are skipped, so running a half-published release again
    uploads what is missing instead of failing on what is there.
    """
    for index in PackageIndex:
        step = workflow.publishing_to(index).step_using(PublishAction.PUBLISH)
        assert step.inputs["skip-existing"] is True
