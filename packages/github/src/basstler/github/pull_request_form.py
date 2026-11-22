"""
GitHub's form opening a pull request, with its title and description filled in from its
address.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Mapping
from dataclasses import dataclass
from itertools import accumulate
from urllib.parse import quote

from basstler.class_property import classproperty
from basstler.github.pull_request_ends import PullRequestOpening
from basstler.github.web_form import PrefilledForm, UrlQueryParameter

# %% the form's parameters


class PullRequestFormParameter(UrlQueryParameter):
    """
    The query parameters of a compare-and-create link.
    """

    EXPAND = "expand"
    """
    Opens the pull request form rather than only the comparison.
    """

    TITLE = "title"
    """
    The title to prefill.
    """

    BODY = "body"
    """
    The description to prefill.
    """


# %% the filled-in form


@dataclass(frozen=True)
class PrefilledPullRequestLink:
    """
    A link opening the pull request form with its title and description filled in.
    """

    url: str
    """
    The compare-and-create URL, ready to open.
    """

    body_was_truncated: bool
    """
    Whether the description had to be shortened to fit the URL.
    """


@dataclass(frozen=True)
class PullRequestForm(PrefilledForm, PullRequestOpening):
    """
    The pull request form joining two branches, filled in from its address.

    The prefill travels in the query string, so an unencoded character truncates it and
    an oversized one is discarded whole by the server - both silently, so
    :attr:`link` shortens :attr:`body` to fit.
    """

    @classproperty
    def url_character_limit(cls) -> int:
        """
        Longest URL to build, the conventional 8 KiB request-line limit servers accept.
        """
        return 8192

    @classproperty
    def truncation_marker(cls) -> str:
        """
        Appended to a body that had to be shortened, so the cut is visible in the
        prefill.
        """
        return "..."

    @property
    def page_url(self) -> str:
        return self.compare_url

    @property
    def filled_fields(self) -> Mapping[UrlQueryParameter, str]:
        return self._fields_with_description(self.body)

    @property
    def url_without_description(self) -> str:
        """
        The form's address with the title alone filled in, the shortest it can be.
        """
        return self.url_filling(self._fields_with_description(""))

    @property
    def link(self) -> PrefilledPullRequestLink | None:
        """
        The link with :attr:`body` filled in, shortened to fit
        :attr:`url_character_limit`; ``None`` when even the title does not fit.
        """
        if len(self.url) <= self.url_character_limit:
            return PrefilledPullRequestLink(self.url, body_was_truncated=False)
        marked = self.url_filling(self._fields_with_description(self.truncation_marker))
        room = self.url_character_limit - len(marked)
        if room < 0:
            return None
        encoded_lengths = accumulate(
            len(quote(character, safe="")) for character in self.body
        )
        kept = bisect_right(list(encoded_lengths), room)
        return PrefilledPullRequestLink(
            self.url_filling(
                self._fields_with_description(self.body[:kept] + self.truncation_marker)
            ),
            body_was_truncated=True,
        )

    def _fields_with_description(
        self, description: str
    ) -> dict[UrlQueryParameter, str]:
        """
        :param description: The description to prefill.
        :return: The fields filling in :attr:`title` and *description*.
        """
        return {
            PullRequestFormParameter.EXPAND: "1",
            PullRequestFormParameter.TITLE: self.title,
            PullRequestFormParameter.BODY: description,
        }
