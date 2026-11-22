"""
Deploying an instance to Cloud Run, with its secrets in Secret Manager and its image
pulled from the GitHub Container Registry through Artifact Registry.
"""

from __future__ import annotations

import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from basstler.environment import HubInstanceVariable
from basstler.hub_server.exceptions import (
    GoogleCloudCommandFailed,
    GoogleCloudNotInstalled,
    UnsupportedImageRegistry,
)

# %% vocabulary

GOOGLE_CLOUD_PROGRAM = "gcloud"
"""
The Google Cloud command line's program.
"""

GITHUB_CONTAINER_REGISTRY = "ghcr.io"
"""
The host of the GitHub Container Registry, which the release publishes the image to.
"""

DEFAULT_COMPUTE_ACCOUNT_DOMAIN = "developer.gserviceaccount.com"
"""
The domain of a project's default compute account, named after the project's number.
"""

ARTIFACT_REGISTRY_DOCKER_HOST_SUFFIX = "docker.pkg.dev"
"""
What the host of a region's Artifact Registry container repositories ends with.
"""

SERVICE_ACCOUNT_MEMBER_PREFIX = "serviceAccount"
"""
The kind an access policy's member names a service account with.
"""

SINGLE_INSTANCE = 1
"""
How many instances a deployment runs at most: one, until instances share their state.
"""


class GoogleCloudCommand(StrEnum):
    """
    The words of the ``gcloud`` commands a deployment runs.
    """

    SERVICES = "services"
    ENABLE = "enable"
    PROJECTS = "projects"
    SECRETS = "secrets"
    VERSIONS = "versions"
    ARTIFACTS = "artifacts"
    REPOSITORIES = "repositories"
    RUN = "run"
    DESCRIBE = "describe"
    CREATE = "create"
    ADD = "add"
    ADD_POLICY_BINDING = "add-iam-policy-binding"
    DEPLOY = "deploy"


class GoogleCloudFlag(StrEnum):
    """
    The ``gcloud`` flags a deployment passes, each written ``--flag=value``.
    """

    PROJECT = "--project"
    REGION = "--region"
    LOCATION = "--location"
    FORMAT = "--format"
    DATA_FILE = "--data-file"
    REPLICATION_POLICY = "--replication-policy"
    MEMBER = "--member"
    ROLE = "--role"
    REPOSITORY_FORMAT = "--repository-format"
    MODE = "--mode"
    REMOTE_DOCKER_REPOSITORY = "--remote-docker-repo"
    IMAGE = "--image"
    SERVICE_ACCOUNT = "--service-account"
    MAXIMUM_INSTANCES = "--max-instances"
    SET_ENVIRONMENT_VARIABLES = "--set-env-vars"
    SET_SECRETS = "--set-secrets"
    ALLOW_UNAUTHENTICATED = "--allow-unauthenticated"
    QUIET = "--quiet"

    def given(self, value: object) -> str:
        """
        :return: This flag given *value*.
        """
        return f"{self}={value}"


class GoogleCloudService(StrEnum):
    """
    The Google Cloud APIs a deployment uses, enabled before it uses them.
    """

    CLOUD_RUN = "run.googleapis.com"
    SECRET_MANAGER = "secretmanager.googleapis.com"
    ARTIFACT_REGISTRY = "artifactregistry.googleapis.com"


class GoogleCloudValue(StrEnum):
    """
    The fixed values a deployment gives ``gcloud`` flags.
    """

    PROJECT_NUMBER_FORMAT = "value(projectNumber)"
    """
    Prints only a project's number.
    """

    AUTOMATIC_REPLICATION = "automatic"
    """
    Lets Secret Manager choose where a secret is replicated.
    """

    SECRET_ACCESSOR_ROLE = "roles/secretmanager.secretAccessor"
    """
    Reads a secret's versions, all a running instance needs of it.
    """

    DOCKER_FORMAT = "docker"
    """
    An Artifact Registry repository holding container images.
    """

    REMOTE_REPOSITORY_MODE = "remote-repository"
    """
    An Artifact Registry repository that proxies another registry.
    """

    LATEST_VERSION = "latest"
    """
    A secret's newest version, which an instance reads at each start.
    """


# %% running gcloud


@dataclass(frozen=True)
class CommandResult:
    """
    What a finished command reported.
    """

    status: int
    """
    Its exit status.
    """

    output: str
    """
    What it wrote to standard output.
    """

    error: str
    """
    What it wrote to standard error.
    """


class GoogleCloudCommandLine(ABC):
    """
    The ``gcloud`` command line a deployment runs its commands through.
    """

    @abstractmethod
    def run(self, arguments: tuple[str, ...]) -> CommandResult:
        """
        :param arguments: The command's arguments, without the program.
        :return: What the command reported.
        """

    def output_of(self, arguments: tuple[str, ...]) -> str:
        """
        :return: What the command printed, without surrounding whitespace.
        :raise GoogleCloudCommandFailed: When it fails.
        """
        result = self.run(arguments)
        if result.status != 0:
            raise GoogleCloudCommandFailed(
                result.status, result.error, (GOOGLE_CLOUD_PROGRAM, *arguments)
            )
        return result.output.strip()

    def succeeds(self, arguments: tuple[str, ...]) -> bool:
        """
        :return: Whether the command exits with success.
        """
        return self.run(arguments).status == 0


class InstalledGoogleCloud(GoogleCloudCommandLine):
    """
    The ``gcloud`` installed on this machine, signed in as whoever runs the deployment.
    """

    def run(self, arguments: tuple[str, ...]) -> CommandResult:
        program = shutil.which(GOOGLE_CLOUD_PROGRAM)
        if program is None:
            raise GoogleCloudNotInstalled()
        completed = subprocess.run(
            (program, *arguments), capture_output=True, encoding="utf-8", check=False
        )
        return CommandResult(completed.returncode, completed.stdout, completed.stderr)


# %% what is deployed


@dataclass(frozen=True)
class GitHubContainerImage:
    """
    An image in the GitHub Container Registry.
    """

    path: str
    """
    The image's path within the registry, with its tag.
    """

    @classmethod
    def from_reference(cls, reference: str) -> GitHubContainerImage:
        """
        :param reference: A reference such as ``ghcr.io/<owner>/<repository>/<image>:<tag>``.
        :raise UnsupportedImageRegistry: When the image is in another registry.
        """
        registry, separator, path = reference.partition("/")
        if registry != GITHUB_CONTAINER_REGISTRY or not separator:
            raise UnsupportedImageRegistry(reference, GITHUB_CONTAINER_REGISTRY)
        return cls(path)


@dataclass(frozen=True)
class SecretManagerSecret:
    """
    The Secret Manager secret holding one instance setting.
    """

    setting: HubInstanceVariable
    """
    The setting it holds, which the instance reads from the variable of that name.
    """

    file: Path | None = None
    """
    A local file whose content becomes the secret's newest version; none keeps the
    versions it has.
    """

    @property
    def secret_name(self) -> str:
        """
        The secret's name: the setting's variable in lower case, words joined by hyphens.
        """
        return self.setting.value.lower().replace("_", "-")


@dataclass(frozen=True)
class CloudRunDeployment:
    """
    One instance deployed as a Cloud Run service of a Google Cloud project.
    """

    project: str
    """
    The Google Cloud project the service runs in.
    """

    region: str
    """
    The region the service, and the repository proxying its image, are in.
    """

    service: str
    """
    The Cloud Run service's name.
    """

    image: GitHubContainerImage
    """
    The image the service runs.
    """

    app_id: int
    """
    The numeric ID of the GitHub App the instance acts as.
    """

    secrets: tuple[SecretManagerSecret, ...]
    """
    The secrets the instance reads its private key and webhook secret from.
    """

    service_account: str | None = None
    """
    The account the service runs as; none runs it as the project's default compute
    account.
    """

    proxy_repository: str = "ghcr"
    """
    The Artifact Registry repository that proxies the GitHub Container Registry.
    """

    command_line: GoogleCloudCommandLine = field(default_factory=InstalledGoogleCloud)
    """
    The ``gcloud`` the deployment runs its commands through.
    """

    def deploy(self) -> None:
        """
        Enable the APIs used, upload the secrets given as files, let the service's
        account read every secret, make sure the proxy repository exists, and deploy.
        """
        self.command_line.output_of(
            (
                GoogleCloudCommand.SERVICES,
                GoogleCloudCommand.ENABLE,
                *GoogleCloudService,
                GoogleCloudFlag.PROJECT.given(self.project),
            )
        )
        account = self.runtime_account()
        for secret in self.secrets:
            self.upload(secret)
            self.grant_access(secret, account)
        self.create_proxy_repository()
        self.command_line.output_of(self.deploy_arguments(account))

    def runtime_account(self) -> str:
        """
        :return: :attr:`service_account`, else the project's default compute account.
        """
        if self.service_account is not None:
            return self.service_account
        number = self.command_line.output_of(
            (
                GoogleCloudCommand.PROJECTS,
                GoogleCloudCommand.DESCRIBE,
                self.project,
                GoogleCloudFlag.FORMAT.given(GoogleCloudValue.PROJECT_NUMBER_FORMAT),
            )
        )
        return f"{number}-compute@{DEFAULT_COMPUTE_ACCOUNT_DOMAIN}"

    def upload(self, secret: SecretManagerSecret) -> None:
        """
        Add the secret's file as its newest version, creating the secret if it has none.
        """
        if secret.file is None:
            return
        project = GoogleCloudFlag.PROJECT.given(self.project)
        data = GoogleCloudFlag.DATA_FILE.given(secret.file)
        exists = self.command_line.succeeds(
            (
                GoogleCloudCommand.SECRETS,
                GoogleCloudCommand.DESCRIBE,
                secret.secret_name,
                project,
            )
        )
        if exists:
            self.command_line.output_of(
                (
                    GoogleCloudCommand.SECRETS,
                    GoogleCloudCommand.VERSIONS,
                    GoogleCloudCommand.ADD,
                    secret.secret_name,
                    project,
                    data,
                )
            )
            return
        self.command_line.output_of(
            (
                GoogleCloudCommand.SECRETS,
                GoogleCloudCommand.CREATE,
                secret.secret_name,
                project,
                data,
                GoogleCloudFlag.REPLICATION_POLICY.given(
                    GoogleCloudValue.AUTOMATIC_REPLICATION
                ),
            )
        )

    def grant_access(self, secret: SecretManagerSecret, account: str) -> None:
        """
        Let *account* read the secret's versions.
        """
        self.command_line.output_of(
            (
                GoogleCloudCommand.SECRETS,
                GoogleCloudCommand.ADD_POLICY_BINDING,
                secret.secret_name,
                GoogleCloudFlag.PROJECT.given(self.project),
                GoogleCloudFlag.MEMBER.given(
                    f"{SERVICE_ACCOUNT_MEMBER_PREFIX}:{account}"
                ),
                GoogleCloudFlag.ROLE.given(GoogleCloudValue.SECRET_ACCESSOR_ROLE),
            )
        )

    def create_proxy_repository(self) -> None:
        """
        Create the repository proxying the GitHub Container Registry, unless it exists.
        """
        location = (
            GoogleCloudFlag.PROJECT.given(self.project),
            GoogleCloudFlag.LOCATION.given(self.region),
        )
        repository = (GoogleCloudCommand.ARTIFACTS, GoogleCloudCommand.REPOSITORIES)
        if self.command_line.succeeds(
            (*repository, GoogleCloudCommand.DESCRIBE, self.proxy_repository, *location)
        ):
            return
        self.command_line.output_of(
            (
                *repository,
                GoogleCloudCommand.CREATE,
                self.proxy_repository,
                *location,
                GoogleCloudFlag.REPOSITORY_FORMAT.given(GoogleCloudValue.DOCKER_FORMAT),
                GoogleCloudFlag.MODE.given(GoogleCloudValue.REMOTE_REPOSITORY_MODE),
                GoogleCloudFlag.REMOTE_DOCKER_REPOSITORY.given(
                    f"https://{GITHUB_CONTAINER_REGISTRY}"
                ),
            )
        )

    @property
    def proxied_image(self) -> str:
        """
        The image's address through the proxy repository, which Cloud Run can pull.
        """
        return (
            f"{self.region}-{ARTIFACT_REGISTRY_DOCKER_HOST_SUFFIX}/{self.project}/"
            f"{self.proxy_repository}/"
            f"{self.image.path}"
        )

    def deploy_arguments(self, account: str) -> tuple[str, ...]:
        """
        :return: The command deploying the service, running as *account*.
        """
        secrets = ",".join(
            f"{secret.setting}={secret.secret_name}:{GoogleCloudValue.LATEST_VERSION}"
            for secret in self.secrets
        )
        return (
            GoogleCloudCommand.RUN,
            GoogleCloudCommand.DEPLOY,
            self.service,
            GoogleCloudFlag.PROJECT.given(self.project),
            GoogleCloudFlag.REGION.given(self.region),
            GoogleCloudFlag.IMAGE.given(self.proxied_image),
            GoogleCloudFlag.SERVICE_ACCOUNT.given(account),
            GoogleCloudFlag.MAXIMUM_INSTANCES.given(SINGLE_INSTANCE),
            GoogleCloudFlag.SET_ENVIRONMENT_VARIABLES.given(
                f"{HubInstanceVariable.APP_ID}={self.app_id}"
            ),
            GoogleCloudFlag.SET_SECRETS.given(secrets),
            GoogleCloudFlag.ALLOW_UNAUTHENTICATED,
            GoogleCloudFlag.QUIET,
        )
