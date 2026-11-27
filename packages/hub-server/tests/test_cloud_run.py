"""
Tests for :mod:`basstler.hub_server.cloud_run`: the ``gcloud`` commands a Cloud Run
deployment runs, recorded instead of run.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from basstler.environment import HubInstanceVariable
from basstler.hub_server.cloud_run import (
    GITHUB_CONTAINER_REGISTRY,
    GOOGLE_CLOUD_PROGRAM,
    SINGLE_INSTANCE,
    CloudRunDeployment,
    CommandResult,
    GitHubContainerImage,
    GoogleCloudCommand,
    GoogleCloudFlag,
    GoogleCloudService,
    GoogleCloudValue,
    SecretManagerSecret,
)
from basstler.hub_server.exceptions import (
    GoogleCloudCommandFailed,
    UnsupportedImageRegistry,
)

from .recorded_google_cloud import RecordingGoogleCloud

IMAGE_PATH = "an-owner/a-repository/basstler-hub-server:1.2.3"
"""
The path, within the GitHub Container Registry, of the image every test deploys.
"""

# %% a deployment


@pytest.fixture
def google_cloud() -> RecordingGoogleCloud:
    """
    A command line on which every secret and repository already exists.
    """
    return RecordingGoogleCloud()


@pytest.fixture
def deployment(
    google_cloud: RecordingGoogleCloud, tmp_path: Path
) -> CloudRunDeployment:
    """
    A deployment uploading its private key from a file and keeping its webhook secret.
    """
    return CloudRunDeployment(
        project="a-project",
        region="europe-west1",
        service="plan-service",
        image=GitHubContainerImage(IMAGE_PATH),
        app_id=1234,
        secrets=(
            SecretManagerSecret(
                HubInstanceVariable.PRIVATE_KEY, tmp_path / "private-key.pem"
            ),
            SecretManagerSecret(HubInstanceVariable.WEBHOOK_SECRET),
        ),
        command_line=google_cloud,
    )


def deploy_command(google_cloud: RecordingGoogleCloud) -> tuple[str, ...]:
    """
    :return: The one service deployment the command line recorded.
    """
    (command,) = google_cloud.commands_starting_with(
        GoogleCloudCommand.RUN, GoogleCloudCommand.DEPLOY
    )
    return command


# %% the service


def test_the_apis_a_deployment_uses_are_enabled_first(
    deployment: CloudRunDeployment, google_cloud: RecordingGoogleCloud
):
    """
    A new project has none of them enabled, and every later command needs one.
    """
    deployment.deploy()

    assert google_cloud.commands[0][:2] == (
        GoogleCloudCommand.SERVICES,
        GoogleCloudCommand.ENABLE,
    )
    assert set(GoogleCloudService) <= set(google_cloud.commands[0])


def test_the_service_runs_one_instance_at_most(
    deployment: CloudRunDeployment, google_cloud: RecordingGoogleCloud
):
    """
    One instance at first, until instances share their state.
    """
    deployment.deploy()

    assert GoogleCloudFlag.MAXIMUM_INSTANCES.given(SINGLE_INSTANCE) in deploy_command(
        google_cloud
    )


def test_the_service_reads_each_secret_from_its_latest_version(
    deployment: CloudRunDeployment, google_cloud: RecordingGoogleCloud
):
    """
    Each setting's variable is filled from its secret, so a new version takes effect at
    the next deployment.
    """
    deployment.deploy()

    assert GoogleCloudFlag.SET_SECRETS.given(
        f"{HubInstanceVariable.PRIVATE_KEY}=basstler-hub-private-key:latest,"
        f"{HubInstanceVariable.WEBHOOK_SECRET}=basstler-hub-webhook-secret:latest"
    ) in deploy_command(google_cloud)


def test_the_app_id_is_a_plain_variable(
    deployment: CloudRunDeployment, google_cloud: RecordingGoogleCloud
):
    """
    The App's ID is no secret, so it is set as it is.
    """
    deployment.deploy()

    assert GoogleCloudFlag.SET_ENVIRONMENT_VARIABLES.given(
        f"{HubInstanceVariable.APP_ID}={deployment.app_id}"
    ) in deploy_command(google_cloud)


def test_the_service_answers_github_without_a_google_identity(
    deployment: CloudRunDeployment, google_cloud: RecordingGoogleCloud
):
    """
    GitHub's deliveries carry no Google credential; the webhook signature is their
    check.
    """
    deployment.deploy()

    assert GoogleCloudFlag.ALLOW_UNAUTHENTICATED in deploy_command(google_cloud)


# %% the image


def test_the_image_is_pulled_through_the_proxy_repository(
    deployment: CloudRunDeployment, google_cloud: RecordingGoogleCloud
):
    """
    Cloud Run cannot pull from the GitHub Container Registry, so it pulls the same path
    from the region's repository proxying it.
    """
    deployment.deploy()

    assert deployment.proxied_image == (
        f"europe-west1-docker.pkg.dev/a-project/ghcr/{IMAGE_PATH}"
    )
    assert GoogleCloudFlag.IMAGE.given(deployment.proxied_image) in deploy_command(
        google_cloud
    )


def test_a_missing_proxy_repository_is_created(
    deployment: CloudRunDeployment, google_cloud: RecordingGoogleCloud
):
    """
    The first deployment in a region creates the repository proxying the registry.
    """
    google_cloud.absent = frozenset({deployment.proxy_repository})

    deployment.deploy()

    (create,) = google_cloud.commands_starting_with(
        GoogleCloudCommand.ARTIFACTS,
        GoogleCloudCommand.REPOSITORIES,
        GoogleCloudCommand.CREATE,
    )
    assert GoogleCloudFlag.MODE.given(GoogleCloudValue.REMOTE_REPOSITORY_MODE) in create
    assert (
        GoogleCloudFlag.REMOTE_DOCKER_REPOSITORY.given(
            f"https://{GITHUB_CONTAINER_REGISTRY}"
        )
        in create
    )


def test_an_existing_proxy_repository_is_kept(
    deployment: CloudRunDeployment, google_cloud: RecordingGoogleCloud
):
    """
    A later deployment reuses the repository.
    """
    deployment.deploy()

    assert not google_cloud.commands_starting_with(
        GoogleCloudCommand.ARTIFACTS,
        GoogleCloudCommand.REPOSITORIES,
        GoogleCloudCommand.CREATE,
    )


def test_an_image_in_the_github_container_registry_is_read_as_its_path():
    """
    The path is what the proxy repository serves the image under.
    """
    reference = f"{GITHUB_CONTAINER_REGISTRY}/{IMAGE_PATH}"

    assert GitHubContainerImage.from_reference(reference) == GitHubContainerImage(
        IMAGE_PATH
    )


@pytest.mark.parametrize(
    "reference",
    [f"docker.io/{IMAGE_PATH}", GITHUB_CONTAINER_REGISTRY, IMAGE_PATH],
)
def test_an_image_outside_the_github_container_registry_is_refused(reference: str):
    """
    The proxy repository serves only that registry.
    """
    with pytest.raises(UnsupportedImageRegistry):
        GitHubContainerImage.from_reference(reference)


# %% the secrets


def test_a_secret_given_as_a_file_that_exists_gets_a_new_version(
    deployment: CloudRunDeployment, google_cloud: RecordingGoogleCloud
):
    """
    Redeploying with a new key replaces the one the service reads.
    """
    deployment.deploy()

    (added,) = google_cloud.commands_starting_with(
        GoogleCloudCommand.SECRETS, GoogleCloudCommand.VERSIONS, GoogleCloudCommand.ADD
    )
    (uploaded, _) = deployment.secrets
    assert added[3] == uploaded.secret_name
    assert GoogleCloudFlag.DATA_FILE.given(uploaded.file) in added


def test_a_secret_given_as_a_file_that_is_missing_is_created(
    deployment: CloudRunDeployment, google_cloud: RecordingGoogleCloud
):
    """
    The first deployment creates the secret from the file.
    """
    (uploaded, _) = deployment.secrets
    google_cloud.absent = frozenset({uploaded.secret_name})

    deployment.deploy()

    (created,) = google_cloud.commands_starting_with(
        GoogleCloudCommand.SECRETS, GoogleCloudCommand.CREATE
    )
    assert created[2] == uploaded.secret_name
    assert GoogleCloudFlag.DATA_FILE.given(uploaded.file) in created


def test_a_secret_given_without_a_file_keeps_its_versions(
    deployment: CloudRunDeployment, google_cloud: RecordingGoogleCloud
):
    """
    A secret already in Secret Manager is deployed as it is.
    """
    (_, kept) = deployment.secrets

    deployment.deploy()

    assert not any(
        kept.secret_name in command
        for command in google_cloud.commands
        if GoogleCloudCommand.VERSIONS in command
        or GoogleCloudCommand.CREATE in command
    )


def test_the_runtime_account_may_read_every_secret(
    deployment: CloudRunDeployment, google_cloud: RecordingGoogleCloud
):
    """
    The service fails to start on a secret its account cannot read.
    """
    deployment.deploy()

    granted = google_cloud.commands_starting_with(
        GoogleCloudCommand.SECRETS, GoogleCloudCommand.ADD_POLICY_BINDING
    )
    assert [command[2] for command in granted] == [
        secret.secret_name for secret in deployment.secrets
    ]
    assert all(
        GoogleCloudFlag.ROLE.given(GoogleCloudValue.SECRET_ACCESSOR_ROLE) in command
        for command in granted
    )


# %% the account the service runs as


def test_the_service_runs_as_the_projects_default_compute_account(
    deployment: CloudRunDeployment, google_cloud: RecordingGoogleCloud
):
    """
    Cloud Run's own default, named after the project's number.
    """
    deployment.deploy()

    assert GoogleCloudFlag.SERVICE_ACCOUNT.given(
        f"{google_cloud.project_number}-compute@developer.gserviceaccount.com"
    ) in deploy_command(google_cloud)


def test_a_given_service_account_is_used_as_it_is(
    deployment: CloudRunDeployment, google_cloud: RecordingGoogleCloud
):
    """
    An account given is not looked up.
    """
    account = "plan-service@a-project.iam.gserviceaccount.com"

    replace(deployment, service_account=account).deploy()

    assert GoogleCloudFlag.SERVICE_ACCOUNT.given(account) in deploy_command(
        google_cloud
    )
    assert not google_cloud.commands_starting_with(GoogleCloudCommand.PROJECTS)


# %% failures


class FailingDeployment(RecordingGoogleCloud):
    """
    A command line on which deploying the service is refused.
    """

    def run(self, arguments: tuple[str, ...]) -> CommandResult:
        if GoogleCloudCommand.DEPLOY in arguments:
            return CommandResult(status=1, output="", error="PERMISSION_DENIED")
        return super().run(arguments)


def test_a_refused_command_stops_the_deployment(deployment: CloudRunDeployment):
    """
    A failure is reported with the command that failed and what gcloud said.
    """
    with pytest.raises(GoogleCloudCommandFailed) as raised:
        replace(deployment, command_line=FailingDeployment()).deploy()

    assert raised.value.arguments[:3] == (
        GOOGLE_CLOUD_PROGRAM,
        GoogleCloudCommand.RUN,
        GoogleCloudCommand.DEPLOY,
    )
