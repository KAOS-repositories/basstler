"""
Tests for the workflow that publishes a release's distributions to PyPI: that it follows
a finished release and publishes through trusted publishing alone.
"""

from __future__ import annotations

import pytest
import yaml
from basstler.github.workflows import ActivityType
from basstler.packaging.package_index import PackageIndex
from basstler.package_map import Distribution
from basstler.packaging.publish_workflow import (
    ContainerRegistryPermission,
    IdentityTokenPermission,
    PublishAction,
    PublishActionInput,
    PublishWorkflow,
)
from basstler.text_file import TextFile

from basstler_testing.constants.paths import RepositoryLocation

from .publish_jobs import PublishJobName, PublishStepId

# %% the workflow


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


def test_each_distribution_publishes_from_an_environment_of_its_own(
    workflow: PublishWorkflow,
):
    """
    PyPI takes a pending trusted publisher for one new project per environment, so each
    distribution's publisher names its own.
    """
    publish = workflow.jobs[PublishJobName.PUBLISH]
    (variable,) = publish.strategy.matrix

    assert publish.environment == PackageIndex.PYPI.publishing_environment(
        f"${{{{ matrix.{variable} }}}}"
    )


def test_the_publish_runs_once_for_each_distribution_the_build_lists(
    workflow: PublishWorkflow,
):
    """
    The matrix is the build's list, so a new distribution needs no change here.
    """
    (output,) = workflow.jobs[PublishJobName.BUILD].outputs
    (distributions,) = workflow.jobs[PublishJobName.PUBLISH].strategy.matrix.values()

    assert distributions == (
        f"${{{{ fromJSON(needs.{PublishJobName.BUILD}.outputs.{output}) }}}}"
    )


def test_a_distribution_that_fails_to_publish_leaves_the_others_publishing(
    workflow: PublishWorkflow,
):
    """
    One refused upload, such as a name whose publisher is missing, cancels no other.
    """
    assert workflow.jobs[PublishJobName.PUBLISH].strategy.fail_fast is False


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


# %% the plan service's image


def test_the_image_is_published_only_for_a_commit_a_release_tags(
    workflow: PublishWorkflow,
):
    """
    It waits for the build, which stops at a commit no release tags, and is named after
    the exact tag of the commit it checks out.
    """
    image = workflow.jobs[PublishJobName.PUBLISH_IMAGE]
    push = image.identified_step(PublishStepId.PUSH_IMAGE)

    assert image.needs == [PublishJobName.BUILD]
    assert "git describe --tags --exact-match" in push.run


def test_the_image_is_built_at_the_release_version(workflow: PublishWorkflow):
    """
    The checkout copied into the build has no history, so the version is passed in.
    """
    push = workflow.jobs[PublishJobName.PUBLISH_IMAGE].identified_step(
        PublishStepId.PUSH_IMAGE
    )
    dockerfile = RepositoryLocation.HUB_SERVER_DOCKERFILE.relative_to(
        RepositoryLocation.ROOT
    )

    assert f"-f {dockerfile.as_posix()}" in push.run
    assert "--build-arg VERSION=" in push.run


def test_the_image_is_named_after_the_repository_it_is_published_from(
    workflow: PublishWorkflow,
):
    """
    A fork publishes its own image under its own name; no owner is written down.
    """
    push = workflow.jobs[PublishJobName.PUBLISH_IMAGE].identified_step(
        PublishStepId.PUSH_IMAGE
    )

    assert f"ghcr.io/${{GITHUB_REPOSITORY,,}}/{Distribution.HUB_SERVER}" in push.run


def test_only_the_job_that_pushes_the_image_may_write_packages(
    workflow: PublishWorkflow,
):
    """
    The run's own token pushes the image, and no other job gets that permission.
    """
    granting = {
        name
        for name, job in workflow.jobs.items()
        if job.permissions.get(ContainerRegistryPermission.SCOPE)
        == ContainerRegistryPermission.LEVEL
    }

    assert granting == {PublishJobName.PUBLISH_IMAGE}
    assert ContainerRegistryPermission.SCOPE not in workflow.permissions
