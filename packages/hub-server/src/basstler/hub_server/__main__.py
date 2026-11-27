"""
The plan service's command line: serve an instance, or deploy one to Cloud Run.

Usage::

    python -m basstler.hub_server serve
    python -m basstler.hub_server deploy-cloud-run --project <project> --region <region> \\
        --service <service> --image ghcr.io/<owner>/<repository>/basstler-hub-server:<tag> \\
        --app-id <id> [--private-key-file <pem>] [--webhook-secret-file <file>]
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

import uvicorn
from cyclopts import App

from basstler.environment import ContainerHostVariable, HubInstanceVariable
from basstler.hub_server.application import HubServer
from basstler.hub_server.cloud_run import (
    CloudRunDeployment,
    GitHubContainerImage,
    SecretManagerSecret,
)
from basstler.hub_server.configuration import InstanceConfiguration
from basstler.standard_streams import StandardStreamHandler

logger = StandardStreamHandler.logger_for(__name__)
"""
This module's logger, which is also what its commands print through.
"""

DEFAULT_PORT = 8080
"""
The port an instance listens on when its host names none, the one Cloud Run names.
"""

# %% commands


class Command(StrEnum):
    """
    Every command this tool answers.
    """

    SERVE = "serve"
    """
    Serve an instance configured from the environment.
    """

    DEPLOY_CLOUD_RUN = "deploy-cloud-run"
    """
    Deploy an instance as a Cloud Run service.
    """


hub_server_app = App(
    name="basstler.hub_server",
    help="The plan service: serve an instance, or deploy one.",
)
"""
This module's command line: one command per :class:`Command`.
"""


@hub_server_app.command(name=Command.SERVE)
def serve(host: str = "0.0.0.0", port: int | None = None) -> None:
    """
    Serve an instance until it is stopped.

    :param host: The address to listen on; every interface, as a container needs.
    :param port: The port to listen on; :attr:`ContainerHostVariable.PORT`, else
        :data:`DEFAULT_PORT`.
    """
    server = HubServer(InstanceConfiguration.from_environment())
    if port is None:
        port = int(ContainerHostVariable.PORT.read() or DEFAULT_PORT)
    uvicorn.run(server.application, host=host, port=port)


@hub_server_app.command(name=Command.DEPLOY_CLOUD_RUN)
def deploy_cloud_run(
    *,
    project: str,
    region: str,
    service: str,
    image: str,
    app_id: int,
    private_key_file: Path | None = None,
    webhook_secret_file: Path | None = None,
    service_account: str | None = None,
) -> None:
    """
    Deploy one instance as a Cloud Run service, with its secrets in Secret Manager.

    :param project: The Google Cloud project to deploy to.
    :param region: The region to run the service in.
    :param service: The Cloud Run service's name.
    :param image: The image, in the GitHub Container Registry.
    :param app_id: The numeric ID of the GitHub App the instance acts as.
    :param private_key_file: The App's private key, uploaded as the secret's newest
        version; without it the secret keeps the versions it has.
    :param webhook_secret_file: A file holding the App's webhook secret, uploaded the
        same way.
    :param service_account: The account the service runs as; the project's default
        compute account without it.
    """
    deployment = CloudRunDeployment(
        project=project,
        region=region,
        service=service,
        image=GitHubContainerImage.from_reference(image),
        app_id=app_id,
        secrets=(
            SecretManagerSecret(HubInstanceVariable.PRIVATE_KEY, private_key_file),
            SecretManagerSecret(
                HubInstanceVariable.WEBHOOK_SECRET, webhook_secret_file
            ),
        ),
        service_account=service_account,
    )
    deployment.deploy()
    logger.info(f"Deployed {service} in {project}, running {deployment.proxied_image}.")


# %% entry point

if __name__ == "__main__":
    hub_server_app()
