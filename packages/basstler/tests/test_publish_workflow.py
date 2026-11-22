"""
Tests for the workflow that publishes a release's distributions to PyPI: that it follows
a finished release, publishes through trusted publishing alone, and reaches PyPI only
after TestPyPI took the same files.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

import yaml

from basstler_testing.constants.paths import RepositoryLocation
from basstler_testing.workflow_definition import Workflow, WorkflowJob, WorkflowKey

# %% vocabulary


class PublishJob(StrEnum):
    """
    The jobs of the publish workflow.
    """

    BUILD = "build"
    TEST_PYPI = "publish-testpypi"
    PYPI = "publish-pypi"


class PublishTarget(StrEnum):
    """
    The package indexes a release is published to, in the order they are reached.
    """

    TEST_PYPI = "testpypi"
    PYPI = "pypi"


class PublishAction(StrEnum):
    """
    The actions the workflow uses to hand files over and publish them.
    """

    PUBLISH = "pypa/gh-action-pypi-publish"
    UPLOAD = "actions/upload-artifact"
    DOWNLOAD = "actions/download-artifact"


class PublishKey(StrEnum):
    """
    The keys of the workflow file these tests read beyond the shared definition.
    """

    NEEDS = "needs"
    PERMISSIONS = "permissions"
    ENVIRONMENT = "environment"
    STEPS = "steps"
    WITH = "with"
    USES = "uses"
    RUN = "run"
    ID_TOKEN = "id-token"
    WRITE = "write"
    REPOSITORY_URL = "repository-url"
    SKIP_EXISTING = "skip-existing"
    PASSWORD = "password"
    REF = "ref"
    FETCH_DEPTH = "fetch-depth"
    WORKFLOWS = "workflows"
    TYPES = "types"
    INPUTS = "inputs"
    TAG = "tag"


class UploadAddress(StrEnum):
    """
    Where TestPyPI takes uploads.
    """

    LEGACY_UPLOAD = "https://test.pypi.org/legacy/"


RELEASE_WORKFLOW_NAME = yaml.safe_load(
    RepositoryLocation.RELEASE_WORKFLOW.read_text(encoding="utf-8")
)["name"]
"""
The name the Release workflow declares, which the publish workflow waits for.
"""

# %% reading the workflow


def publish_file() -> dict[Any, Any]:
    """
    :return: The workflow as YAML loads it, which reads the ``on`` key as ``True``.
    """
    return yaml.safe_load(
        RepositoryLocation.PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    )


def raw_job(job: PublishJob) -> dict[str, Any]:
    """
    :param job: One of the workflow's jobs.
    :return: The job as the file writes it.
    """
    return publish_file()[WorkflowKey.JOBS][job]


def job(job: PublishJob) -> WorkflowJob:
    """
    :param job: One of the workflow's jobs.
    :return: The job, parsed.
    """
    return Workflow.read(RepositoryLocation.PUBLISH_WORKFLOW).jobs[job]


def publish_step(target: PublishTarget) -> dict[str, Any]:
    """
    :param target: The index a job publishes to.
    :return: The step of that job which publishes, as the file writes it.
    """
    publishing_job = {
        PublishTarget.TEST_PYPI: PublishJob.TEST_PYPI,
        PublishTarget.PYPI: PublishJob.PYPI,
    }[target]
    (step,) = (
        step
        for step in raw_job(publishing_job)[PublishKey.STEPS]
        if step.get(PublishKey.USES, "").startswith(PublishAction.PUBLISH)
    )
    return step


# %% when it runs


def test_the_workflow_follows_a_finished_release():
    """
    It starts when the Release workflow completes, so a commit that was not released
    publishes nothing.
    """
    trigger = publish_file()[True]["workflow_run"]

    assert trigger[PublishKey.WORKFLOWS] == [RELEASE_WORKFLOW_NAME]
    assert trigger[PublishKey.TYPES] == ["completed"]


def test_a_release_that_failed_publishes_nothing():
    """
    A Release run that failed tagged nothing, so there is nothing to publish.
    """
    assert "github.event.workflow_run.conclusion == 'success'" in (
        job(PublishJob.BUILD).condition
    )


def test_a_tag_can_be_published_by_hand():
    """
    A release whose publishing stopped is finished by naming its tag, since the next
    release run finds nothing new to tag.
    """
    inputs = publish_file()[True]["workflow_dispatch"][PublishKey.INPUTS]

    assert PublishKey.TAG in inputs


# %% what is built


def test_every_distribution_is_built_from_the_tagged_commit_with_its_history():
    """
    The version is read from the tag, which a shallow checkout does not have.
    """
    checkout = raw_job(PublishJob.BUILD)[PublishKey.STEPS][0]

    assert checkout[PublishKey.WITH][PublishKey.FETCH_DEPTH] == 0


def test_the_build_covers_every_member_of_the_workspace():
    """
    One build produces every distribution, so none is left at the previous release.
    """
    build = job(PublishJob.BUILD)

    assert any("uv build --all-packages" in (step.command or "") for step in build.steps)


# %% how it publishes


def test_the_workflow_holds_no_credential():
    """
    Trusted publishing is the only way in: no secret and no token appears in the file.
    """
    source = RepositoryLocation.PUBLISH_WORKFLOW.read_text(encoding="utf-8")

    assert "secrets." not in source
    for target in PublishTarget:
        assert PublishKey.PASSWORD not in publish_step(target).get(PublishKey.WITH, {})


def test_only_the_jobs_that_publish_may_request_an_identity_token():
    """
    The identity token is what proves to the index which workflow publishes, so no other
    job can ask for one.
    """
    granting = {
        name
        for name, declared in publish_file()[WorkflowKey.JOBS].items()
        if declared.get(PublishKey.PERMISSIONS, {}).get(PublishKey.ID_TOKEN)
        == PublishKey.WRITE
    }

    assert granting == {PublishJob.TEST_PYPI, PublishJob.PYPI}
    assert PublishKey.ID_TOKEN not in publish_file().get(PublishKey.PERMISSIONS, {})


def test_each_index_is_published_from_an_environment_of_its_own():
    """
    The index's trusted publisher names the environment, so one index's publisher cannot
    publish to the other.
    """
    assert raw_job(PublishJob.TEST_PYPI)[PublishKey.ENVIRONMENT] == (
        PublishTarget.TEST_PYPI
    )
    assert raw_job(PublishJob.PYPI)[PublishKey.ENVIRONMENT] == PublishTarget.PYPI


def test_testpypi_is_published_to_at_its_own_address():
    """
    The default address of the publish action is PyPI itself.
    """
    step = publish_step(PublishTarget.TEST_PYPI)

    assert step[PublishKey.WITH][PublishKey.REPOSITORY_URL] == (
        UploadAddress.LEGACY_UPLOAD
    )
    assert PublishKey.REPOSITORY_URL not in publish_step(PublishTarget.PYPI).get(
        PublishKey.WITH, {}
    )


def test_pypi_is_reached_only_after_testpypi_took_the_files():
    """
    A release the test index refuses never reaches PyPI.
    """
    assert PublishJob.TEST_PYPI in raw_job(PublishJob.PYPI)[PublishKey.NEEDS]
    assert PublishJob.BUILD in raw_job(PublishJob.TEST_PYPI)[PublishKey.NEEDS]


def test_both_indexes_publish_the_files_the_build_made():
    """
    What TestPyPI took is byte for byte what PyPI gets, since both download the
    build's artifact instead of building again.
    """
    for publishing_job in (PublishJob.TEST_PYPI, PublishJob.PYPI):
        actions = {
            step.action for step in job(publishing_job).steps if step.action
        }
        assert PublishAction.DOWNLOAD in actions
    assert PublishAction.UPLOAD in {
        step.action for step in job(PublishJob.BUILD).steps if step.action
    }


def test_a_publish_that_stopped_can_be_run_again():
    """
    Files an index already holds are skipped, so running a half-published release again
    uploads what is missing instead of failing on what is there.
    """
    for target in PublishTarget:
        assert publish_step(target)[PublishKey.WITH][PublishKey.SKIP_EXISTING] is True
