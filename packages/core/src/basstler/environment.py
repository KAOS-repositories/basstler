"""
The environment variables this package reads, grouped by who sets them.

Every group is an :class:`EnvironmentVariable`, so reading one is the same call
whichever group it belongs to, and a variable is named once rather than typed out where
it is read.
"""

from __future__ import annotations

import os
from enum import StrEnum
from pathlib import Path

from basstler.credential_origin import CredentialOrigin
from basstler.text_file import TextFile


class EnvironmentFlag(StrEnum):
    """
    The values a variable that switches something on or off is set to.
    """

    TRUE = "true"
    """
    The thing the variable stands for is on.
    """


class EnvironmentVariable(StrEnum):
    """
    An environment variable, named by its value.

    The base every group of them extends.
    """

    def read(self) -> str | None:
        """
        :return: The variable's value in this process's environment, or ``None`` when it
            is not set.
        """
        return os.environ.get(self)

    def is_true(self) -> bool:
        """:return: Whether the variable is set to :attr:`EnvironmentFlag.TRUE`."""
        return self.read() == EnvironmentFlag.TRUE


class OperatingSystemVariable(EnvironmentVariable):
    """
    The variables the operating system sets for every process.
    """

    EXECUTABLE_SEARCH_PATH = "PATH"
    """
    The directories a program is searched for in.
    """

    WINDOWS_DIRECTORY = "SYSTEMROOT"
    """
    The Windows installation's own directory, set only on Windows, spelled as Windows
    lists it in a copy of the environment.
    """


class GitBashVariable(EnvironmentVariable):
    """
    The variables Git for Windows' bash (MSYS2) reads before it starts a program.
    """

    ARGUMENT_CONVERSION_EXCLUSIONS = "MSYS2_ARG_CONV_EXCL"
    """
    The ``;``-separated prefixes of the arguments it passes on as written rather than
    rewriting them as Windows paths.
    """


class GitVariable(EnvironmentVariable):
    """
    The variables git reads that this package, or its tests, set for the commands run.
    """

    INDEX_FILE = "GIT_INDEX_FILE"
    """
    The index git stages into, in place of the clone's own.
    """

    CONFIGURATION_COUNT = "GIT_CONFIG_COUNT"
    """
    How many configuration entries the environment passes to git.
    """

    CONFIGURATION_KEY_PREFIX = "GIT_CONFIG_KEY_"
    """
    Followed by an entry's index, names the variable holding that entry's key.
    """

    CONFIGURATION_VALUE_PREFIX = "GIT_CONFIG_VALUE_"
    """
    Followed by an entry's index, names the variable holding that entry's value.
    """

    COMMITTER_DATE = "GIT_COMMITTER_DATE"
    """
    The date git records as a new commit's committer date, in place of the clock's.
    """


class GitHubCredentialVariable(CredentialOrigin, EnvironmentVariable):
    """
    The variables a GitHub token is read from, in the order they are tried.
    """

    GH_TOKEN = "GH_TOKEN"
    """
    The token the ``gh`` CLI reads, preferred where both are set.
    """

    GITHUB_TOKEN = "GITHUB_TOKEN"
    """
    The token GitHub Actions hands a workflow.
    """

    def describe_credential(self) -> str:
        """
        :return: :meth:`CredentialOrigin.describe_credential`: the token in this
            variable.
        """
        return f"the token in {self}"

    def suggest_renewal(self) -> str:
        """
        :return: :meth:`CredentialOrigin.suggest_renewal`: set a valid token in this
            variable.
        """
        return f"Set a valid token in {self}."

    @classmethod
    def first_set(cls) -> GitHubCredentialVariable | None:
        """
        :return: The first variable holding a non-empty token, in the order they are
            tried, or ``None`` when none does.
        """
        return next((variable for variable in cls if variable.read()), None)

    @classmethod
    def first_token(cls) -> str | None:
        """
        :return: The first non-empty token, in the order the variables are tried, or
            ``None`` when none is set.
        """
        variable = cls.first_set()
        return None if variable is None else variable.read()


class GitHubActionsVariable(EnvironmentVariable):
    """
    The variables a GitHub Actions runner sets for the steps it runs.
    """

    STEP_SUMMARY = "GITHUB_STEP_SUMMARY"
    """
    The file a step appends its Markdown job summary to.
    """

    OUTPUT = "GITHUB_OUTPUT"
    """
    The file a step appends its ``<key>=<value>`` outputs to.
    """

    RUNNER_TEMPORARY_DIRECTORY = "RUNNER_TEMP"
    """
    A directory the runner empties for each job, which steps hand files through.
    """

    REPOSITORY_OWNER = "GITHUB_REPOSITORY_OWNER"
    """
    The owner of the repository the workflow runs in.
    """


FILE_VARIABLE_SUFFIX = "_FILE"
"""
What a variable naming a file that holds a setting appends to the setting's own name.
"""


class HubInstanceVariable(EnvironmentVariable):
    """
    The settings a plan service instance is configured with, each given in the variable
    itself or in a file the variable with :data:`FILE_VARIABLE_SUFFIX` appended names.
    """

    APP_ID = "BASSTLER_HUB_APP_ID"
    """
    The numeric ID of the GitHub App the instance acts as.
    """

    PRIVATE_KEY = "BASSTLER_HUB_PRIVATE_KEY"
    """
    The GitHub App's private key, in PEM.
    """

    WEBHOOK_SECRET = "BASSTLER_HUB_WEBHOOK_SECRET"
    """
    The secret GitHub signs the App's webhook deliveries with.
    """

    @property
    def file_variable(self) -> str:
        """
        The variable naming a file that holds this setting, as a container host mounts
        a secret.
        """
        return f"{self}{FILE_VARIABLE_SUFFIX}"

    def read_value_or_file(self) -> str | None:
        """
        :return: The variable's value; else the text of the file :attr:`file_variable`
            names, without the newline ending it; else ``None``.
        """
        value = self.read()
        if value is not None:
            return value
        path = os.environ.get(self.file_variable)
        if path is None:
            return None
        return TextFile(Path(path)).read().removesuffix("\n")


class ContainerHostVariable(EnvironmentVariable):
    """
    The variables a container host sets for the container it runs.
    """

    PORT = "PORT"
    """
    The port the container is expected to listen on.
    """
