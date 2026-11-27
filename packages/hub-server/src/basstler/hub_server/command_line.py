"""
The ``basstler hub-server`` commands: registering the App the service runs as.
"""

from __future__ import annotations

from enum import StrEnum

from cyclopts import App

from basstler.exit_codes import ExitCode
from basstler.hub_server.app_registration import AppRegistration
from basstler.hub_server.secret_store import SecretStore
from basstler.standard_streams import StandardStreamHandler

logger = StandardStreamHandler.logger_for(__name__)
"""
This module's logger, which is also what its commands print through.
"""

# %% names and exit statuses


class HubServerCommand(StrEnum):
    """
    The hub server's command group and its commands, by name.
    """

    GROUP = "hub-server"
    """
    The command group itself.
    """

    REGISTER_APP = "register-app"
    """
    Register the App from the committed manifest.
    """


class HubServerExitCode(ExitCode):
    """
    What a ``hub-server`` command's exit status means.
    """

    SUCCESS = 0
    """
    The command did what it was asked.
    """


# %% the commands

hub_server_app = App(
    name=HubServerCommand.GROUP,
    help="Run the service behind the plan site.",
)
"""
The ``hub-server`` command group.
"""


@hub_server_app.command(name=HubServerCommand.REGISTER_APP)
def register_app(
    owner: str,
    *,
    webhook_url: str,
    homepage_url: str | None = None,
    name: str | None = None,
    personal_account: bool = False,
) -> HubServerExitCode:
    """
    Register the App from the committed manifest through GitHub's manifest flow, and keep
    its key and secrets in the instance's secret directory.

    :param owner: The account or organization that owns the App.
    :param webhook_url: Where GitHub delivers the App's events.
    :param homepage_url: The App's home page; the address the webhook is on by default.
    :param name: The App's name, unique across GitHub; one unique to the owner by default.
    :param personal_account: Whether *owner* is the signed-in user rather than an
        organization.
    :return: :attr:`HubServerExitCode.SUCCESS`; a failure raises instead.
    """
    registration = AppRegistration.for_owner(
        owner,
        webhook_url,
        SecretStore.from_environment(),
        homepage_url,
        name,
        personal_account,
    )
    credentials = registration.register()
    logger.info(
        f"Registered the App {credentials.slug}; its key and secrets are in "
        f"{registration.store.directory}"
    )
    return HubServerExitCode.SUCCESS
