"""
The settings a plan service instance runs with, read from its environment.
"""

from __future__ import annotations

from dataclasses import dataclass

from basstler.environment import HubInstanceVariable
from basstler.hub_server.exceptions import MissingInstanceSetting

# %% the configuration


@dataclass(frozen=True)
class InstanceConfiguration:
    """
    What an instance needs to act as its GitHub App and to trust the App's deliveries.
    """

    app_id: int
    """
    The numeric ID of the GitHub App the instance acts as.
    """

    private_key: str
    """
    The App's private key, in PEM.
    """

    webhook_secret: str
    """
    The secret GitHub signs the App's webhook deliveries with.
    """

    @classmethod
    def from_environment(cls) -> InstanceConfiguration:
        """
        :return: The configuration each :class:`HubInstanceVariable` gives.
        :raise MissingInstanceSetting: When a setting is given neither way.
        """
        return cls(
            app_id=int(cls.read_required_setting(HubInstanceVariable.APP_ID)),
            private_key=cls.read_required_setting(HubInstanceVariable.PRIVATE_KEY),
            webhook_secret=cls.read_required_setting(
                HubInstanceVariable.WEBHOOK_SECRET
            ),
        )

    @staticmethod
    def read_required_setting(setting: HubInstanceVariable) -> str:
        """
        :return: The setting's value, from its variable or its file.
        :raise MissingInstanceSetting: When it is given neither way.
        """
        value = setting.read_value_or_file()
        if value is None:
            raise MissingInstanceSetting(setting)
        return value
