"""
Filling GitHub's new fine-grained token form in from its address, and one token doing
several jobs.
"""

from __future__ import annotations

from dataclasses import replace
from urllib.parse import parse_qs, urlsplit

from basstler.github.actions_secret import ActionsSecret
from basstler.github.token_form import (
    FineGrainedTokenForm,
    PermissionLevel,
    RepositoryPermission,
    SharedToken,
    StoredSecret,
    TokenFormParameter,
    TokenUse,
)
from basstler.github.repository import Repository

# %% the filled-in form

FORM = FineGrainedTokenForm(
    "a token",
    "what it is for",
    "an-owner",
    {RepositoryPermission.PULL_REQUESTS: PermissionLevel.WRITE},
)
"""
A form with every field and one permission filled in.
"""


def test_every_field_and_permission_is_filled_in():
    fields = parse_qs(urlsplit(FORM.url).query)
    assert fields == {
        TokenFormParameter.NAME: [FORM.name],
        TokenFormParameter.DESCRIPTION: [FORM.description],
        TokenFormParameter.RESOURCE_OWNER: [FORM.resource_owner],
        RepositoryPermission.PULL_REQUESTS: [PermissionLevel.WRITE],
    }


# %% one token for several jobs


class SecretOfAJob(ActionsSecret):
    """
    The secrets the jobs these tests join store the token as.
    """

    BUILD = "BUILD_TOKEN"
    """
    Read by the job starting the build.
    """

    REVIEW = "REVIEW_TOKEN"
    """
    Read by the job reading pull requests.
    """


SITE = Repository("an-owner", "site")
"""
A repository whose Actions one job starts.
"""

NOTES = Repository("an-owner", "notes")
"""
The repository storing the token, whose pull requests another job reads.
"""

BUILD = TokenUse(
    "starts the build",
    (SITE,),
    {RepositoryPermission.ACTIONS: PermissionLevel.WRITE},
    SecretOfAJob.BUILD,
    (NOTES,),
)
"""
A job starting a workflow on one repository.
"""

REVIEW = TokenUse(
    "reads pull requests",
    (NOTES,),
    {
        RepositoryPermission.PULL_REQUESTS: PermissionLevel.WRITE,
        RepositoryPermission.CONTENTS: PermissionLevel.READ,
    },
    SecretOfAJob.REVIEW,
    (NOTES,),
)
"""
A job on the same owner's repositories as :data:`BUILD`.
"""


def test_a_job_on_another_owner_s_repositories_is_not_joined():
    elsewhere = replace(REVIEW, repositories=(Repository("someone-else", "notes"),))
    assert SharedToken.from_requested_use("a token", BUILD, (elsewhere,)).uses == (
        BUILD,
    )


def test_the_joined_token_grants_every_job_s_permissions():
    token = SharedToken.from_requested_use("a token", BUILD, (REVIEW,))
    assert token.form.permissions == BUILD.permissions | REVIEW.permissions


def test_a_permission_two_jobs_need_gets_the_broader_level():
    writer = replace(
        BUILD, permissions={RepositoryPermission.CONTENTS: PermissionLevel.WRITE}
    )
    token = SharedToken.from_requested_use("a token", REVIEW, (writer,))
    assert token.form.permissions[RepositoryPermission.CONTENTS] == (
        PermissionLevel.WRITE
    )


def test_the_joined_token_reaches_each_job_s_repository_once():
    token = SharedToken.from_requested_use("a token", BUILD, (REVIEW,))
    assert token.repositories == [SITE, NOTES]


def test_the_joined_token_is_stored_as_every_job_s_secret():
    token = SharedToken.from_requested_use("a token", BUILD, (REVIEW,))
    assert token.secrets == [
        StoredSecret(repository=NOTES, secret=BUILD.secret),
        StoredSecret(repository=NOTES, secret=REVIEW.secret),
    ]


def test_a_token_stored_as_several_secrets_is_asked_for_once():
    command = SharedToken.from_requested_use("a token", BUILD, (REVIEW,)).store_command
    assert (command.count("read -rsp"), command.count("gh secret set")) == (1, 2)


def test_a_token_stored_as_one_secret_is_stored_by_one_gh_command_prompting_for_it():
    """
    ``gh secret set`` asks for the value itself, so no shell prompt wraps it.
    """
    assert SharedToken.from_requested_use("a token", BUILD, ()).store_command == (
        f"gh secret set {BUILD.secret} --repo {NOTES.full_name}"
    )
