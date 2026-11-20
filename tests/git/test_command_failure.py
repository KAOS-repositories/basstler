"""
Tests for what a failed git command tells the person who has to fix it.
"""

from __future__ import annotations

import pytest

from basstler.git.commands import GitCommandFailed, RemoteSubcommand

# %% what the failure suggests


def a_failure_of(*arguments: str) -> GitCommandFailed:
    """
    :param arguments: The git subcommand and its arguments.
    :return: The failure of that command.
    """
    return GitCommandFailed(status=128, detail="it refused", arguments=arguments)


@pytest.mark.parametrize("subcommand", list(RemoteSubcommand))
def test_a_failed_remote_command_suggests_checking_the_remote(
    subcommand: RemoteSubcommand,
):
    failure = a_failure_of(subcommand, "origin")

    assert "remote" in failure.suggest_correction()
    assert failure.call in failure.suggest_correction()


def test_a_failed_local_command_suggests_running_it_to_see_why():
    failure = a_failure_of("for-each-ref", "--merged=upstream/main")

    assert failure.suggest_correction() != a_failure_of("fetch").suggest_correction()
    assert failure.call in failure.suggest_correction()


def test_the_message_names_the_command_its_status_and_what_git_said_then_the_suggestion():
    failure = a_failure_of("fetch", "origin")

    assert str(failure) == (
        f"{failure.call} failed with {failure.status}: {failure.detail}\n"
        f"Suggestion: {failure.suggest_correction()}"
    )
