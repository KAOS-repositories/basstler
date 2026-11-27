"""
Running git for a pass, and deciding what a pass is allowed to publish.

Every command a pass runs goes through :class:`GitCommandRunner`, and every push it
proposes is built as a :class:`ProposedPush` - so whether published history may be
rewritten is decided in one place rather than at each call site.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from functools import cached_property
from pathlib import Path, PurePath, PurePosixPath

from basstler.class_property import classproperty
from basstler.environment import GitVariable
from basstler.exceptions import ExternalCallFailed, UnresolvableReferenceError
from basstler.exit_codes import CommandFailure, StackExitCode
from basstler.locations import CommitScratchFile, RepositoryStateLocation

# %% running git

GIT_TEXT_ENCODING = "utf-8"
"""
The encoding git's output and the files it commits are read and written in.
"""

OBJECT_HEADER_FIELDS = 3
"""
How many fields ``git cat-file --batch`` prints before an object it found: its name,
type and size in bytes.
"""


class ObjectHeaderStatus(StrEnum):
    """
    What ``git cat-file --batch`` prints after a name in place of an object's type and
    size.
    """

    MISSING = "missing"
    """
    The repository has no object of that name.
    """


MERGE_CONFLICT_EXIT_STATUS = 1
"""
The status ``git merge-tree`` exits with when the merge conflicts.
"""


class RemoteSubcommand(StrEnum):
    """
    The git subcommands that talk to a remote, whose failure may be the remote's.
    """

    FETCH = "fetch"
    """
    Updates references from a remote.
    """
    LIST_REMOTE = "ls-remote"
    """
    Lists the references a remote has.
    """
    PUSH = "push"
    """
    Publishes references to a remote.
    """


@dataclass
class GitCommandFailed(CommandFailure, ExternalCallFailed):
    """
    Raised when a git command this module depends on the result of fails.
    """

    @classproperty
    def exit_code(cls) -> StackExitCode:
        """:return: The status this kind of error ends a command with."""
        return StackExitCode.GIT_COMMAND_FAILED

    arguments: tuple[str, ...] = ()
    """
    The git subcommand and its arguments, as invoked.
    """

    @property
    def call(self) -> str:
        """:return: The git command line, as invoked."""
        return f"git {' '.join(self.arguments)}"

    def suggest_correction(self) -> str:
        if self.arguments and self.arguments[0] in set(RemoteSubcommand):
            return (
                f"check that the remote is reachable with this session's credential, "
                f"then run `{self.call}` to see it succeed"
            )
        return f"run `{self.call}` in the checkout to see why git refused it"


@dataclass(frozen=True)
class GitCommandResult:
    """
    One finished git command, whether or not it succeeded.
    """

    arguments: tuple[str, ...]
    """
    The git subcommand and its arguments, as invoked.
    """
    exit_status: int
    """
    The status git exited with.
    """
    output: str
    """
    Git's stripped stdout.
    """
    error_output: str
    """
    Git's stripped stderr.
    """

    @property
    def succeeded(self) -> bool:
        """:return: Whether git exited zero."""
        return self.exit_status == 0

    def raise_if_failed(self) -> GitCommandResult:
        """:return: This result, when the command succeeded.
        :raises GitCommandFailed: When it did not."""
        if not self.succeeded:
            raise GitCommandFailed(
                status=self.exit_status,
                detail=self.error_output,
                arguments=self.arguments,
            )
        return self


@dataclass(frozen=True)
class MergeCommit:
    """
    A commit merging two others, made without touching any branch or the working tree.
    """

    commit: str
    """
    The merge commit, git's conflict markers left in the files it conflicts on.
    """
    conflicted_paths: frozenset[PurePosixPath]
    """
    The files the merge conflicts on, by their path in the merge commit.
    """


# %% what a pass is allowed to publish


@dataclass(frozen=True)
class ProposedPush:
    """
    One publication, and whether it is authorised to overwrite what is published.

    Every push the executor makes is built here, so whether history may be rewritten is
    decided once rather than at each call.
    """

    remote: str
    """
    The remote to publish to.
    """
    refspec: str
    """
    What to publish, as ``<source>:<destination>``.
    """
    with_lease: bool = False
    """
    Whether published history may be overwritten, and then only if the remote is where
    this checkout last saw it.
    """

    @classmethod
    def publishing(
        cls,
        remote: str,
        branch: str,
        strategy: IntegrationStrategy,
        replaces_superseded_merges: bool = False,
    ) -> ProposedPush:
        """
        Build the push that publishes a restacked branch.

        :param remote: The remote to publish to: the fork's.
        :param branch: The branch to publish.
        :param strategy: How its parent was integrated, which authorises a rewrite when
            it is a rebase - and which ``Stack.build`` sets to rebase only from the label.
        :param replaces_superseded_merges: Whether the integration replaced merges that
            only brought in an earlier state of the parent, the one rewrite a merge is
            authorised to make.
        :return: The push.
        """
        return cls(
            remote=remote,
            refspec=f"{branch}:{branch}",
            with_lease=strategy is IntegrationStrategy.REBASE
            or replaces_superseded_merges,
        )


@dataclass
class ObjectStream:
    """
    One ``git cat-file --batch`` kept running in a checkout, answering object names one
    at a time with the objects' contents.
    """

    working_directory: Path
    """
    The checkout whose objects are read.
    """

    @classproperty
    def arguments(cls) -> tuple[str, ...]:
        """
        The git subcommand that reads the objects, and its arguments.
        """
        return ("cat-file", "--batch")

    def __getstate__(self) -> dict[str, Path]:
        """
        :return: The stream without its running command, which a copy of it made in
            another process starts anew.
        """
        return {"working_directory": self.working_directory}

    @cached_property
    def process(self) -> subprocess.Popen[bytes]:
        """
        The running command, which ends once its input closes, at the latest when this
        process exits.
        """
        return subprocess.Popen(
            ["git", *self.arguments],
            cwd=self.working_directory,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def content(self, name: str) -> bytes | None:
        """
        :param name: An object git names, such as ``<commit>:<path>`` for a file.
        :return: The object's content, ``None`` when the repository has no object of
            that name.
        :raises GitCommandFailed: If git has ended or answers the name ambiguously.
        """
        self.process.stdin.write(f"{name}\n".encode(GIT_TEXT_ENCODING))
        self.process.stdin.flush()
        header_line = self.process.stdout.readline()
        header = header_line.split()
        if (
            header
            and header[-1].decode(GIT_TEXT_ENCODING) == ObjectHeaderStatus.MISSING
        ):
            return None
        if len(header) != OBJECT_HEADER_FIELDS:
            detail = header_line or self.process.stderr.read()
            raise GitCommandFailed(
                status=self.process.poll() or 0,
                detail=detail.decode(GIT_TEXT_ENCODING).strip(),
                arguments=self.arguments,
            )
        return self.process.stdout.read(int(header[-1]) + 1)[:-1]


@dataclass(frozen=True)
class GitCommandRunner:
    """
    Runs git in one checkout, reporting failures rather than swallowing them.

    ``stack/checkout.py`` reads git through a helper that returns an empty string when a command
    fails. That is right for derivation, where a missing ref simply means "no answer",
    and wrong here: a push that silently did nothing would be indistinguishable from one
    that worked.
    """

    working_directory: Path
    """
    The checkout every command runs in.
    """

    def attempt(
        self,
        *arguments: str,
        environment: Mapping[str, str] | None = None,
        standard_input: str | None = None,
    ) -> GitCommandResult:
        """
        Run a command whose failure is an expected outcome.

        :param arguments: The git subcommand and its arguments.
        :param environment: Variables to set for this command on top of the process's
            own.
        :param standard_input: What the command reads from standard input, nothing when
            ``None``.
        :return: The finished command.
        """
        completed = subprocess.run(
            ["git", *arguments],
            cwd=self.working_directory,
            capture_output=True,
            encoding=GIT_TEXT_ENCODING,
            env={**os.environ, **(environment or {})},
            input=standard_input,
        )
        return GitCommandResult(
            arguments=arguments,
            exit_status=completed.returncode,
            output=completed.stdout.strip(),
            error_output=completed.stderr.strip(),
        )

    def run(self, *arguments: str, environment: Mapping[str, str] | None = None) -> str:
        """
        Run a command this module depends on the result of.

        :param arguments: The git subcommand and its arguments.
        :param environment: Variables to set for this command on top of the process's
            own.
        :return: Git's stripped stdout.
        :raises GitCommandFailed: If git exits non-zero.
        """
        return (
            self.attempt(*arguments, environment=environment).raise_if_failed().output
        )

    def run_binary(self, *arguments: str, standard_input: bytes = b"") -> bytes:
        """
        Run a command whose output is bytes, such as the content of committed files.

        :param arguments: The git subcommand and its arguments.
        :param standard_input: What the command reads from its standard input.
        :return: Git's stdout, unstripped.
        :raises GitCommandFailed: If git exits non-zero.
        """
        completed = subprocess.run(
            ["git", *arguments],
            cwd=self.working_directory,
            input=standard_input,
            capture_output=True,
        )
        GitCommandResult(
            arguments=arguments,
            exit_status=completed.returncode,
            output="",
            error_output=completed.stderr.decode(GIT_TEXT_ENCODING).strip(),
        ).raise_if_failed()
        return completed.stdout

    def repository_state_path(self, location: RepositoryStateLocation) -> Path:
        """
        :param location: Scratch state kept per repository.
        :return: Where it lives for this checkout's repository, the same from every
            worktree of it.
        """
        common_directory = self.run(
            "rev-parse", "--path-format=absolute", "--git-common-dir"
        )
        return Path(common_directory) / location

    def fetch(self, remote: str, *references: str) -> None:
        """
        Refresh what this checkout knows about a remote.

        :param remote: The remote to fetch from.
        :param references: The branches to fetch, all of them when none is named.
        """
        self.run("fetch", "--quiet", remote, *references)

    def fetch_branch(
        self, location: str, branch: str, tracking_remote: str
    ) -> GitCommandResult:
        """
        Fetch one branch into its tracking ref, leaving ``FETCH_HEAD`` alone.

        :param location: The remote name or URL to fetch from.
        :param branch: The branch to fetch.
        :param tracking_remote: The remote whose tracking refs the branch is kept under.
        :return: The finished fetch, whose failure is an expected outcome.
        """
        return self.attempt(
            "fetch",
            "--quiet",
            "--no-write-fetch-head",
            location,
            f"+refs/heads/{branch}:refs/remotes/{tracking_remote}/{branch}",
        )

    def configured_remote_url(self, remote: str) -> str | None:
        """
        :param remote: A remote's name.
        :return: The URL the clone configures for it, not git's rewrite of it, ``None``
            for no such remote.
        """
        read = self.attempt("config", "--get", f"remote.{remote}.url")
        return read.output if read.succeeded else None

    def commit_or_none(self, reference: str) -> str | None:
        """:param reference: A ref that may not exist.
        :return: The commit it names, or ``None`` if it does not exist."""
        resolved = self.attempt("rev-parse", "--verify", "--quiet", reference)
        return resolved.output if resolved.succeeded else None

    def commit_at(self, reference: str) -> str:
        """:param reference: Any reference git can resolve.
        :return: The commit it names."""
        return self.run("rev-parse", reference)

    def local_commit(self, branch: str) -> str | None:
        """:param branch: A branch name.
        :return: The commit this checkout's own copy of the branch is at, ``None`` when
            it has none."""
        found = self.attempt("rev-parse", "--verify", "--quiet", f"refs/heads/{branch}")
        return found.output if found.succeeded else None

    def restore_branch(self, branch: str, commit: str | None) -> None:
        """
        Put this checkout's own copy of a branch back where it was.

        :param branch: The branch to restore.
        :param commit: Where it was, or ``None`` to have no copy of it.
        """
        reference = f"refs/heads/{branch}"
        if commit is None:
            self.run("update-ref", "-d", reference)
            return
        self.run("update-ref", reference, commit)

    def file_at(self, commit: str, path: str | PurePath) -> str | None:
        """
        :param commit: The commit to read from.
        :param path: The file's path from the commit's root.
        :return: Its text without the final newline, or ``None`` when the commit has
            no such file.
        """
        shown = self.attempt("show", f"{commit}:{PurePosixPath(path)}")
        return shown.output if shown.succeeded else None

    def object_texts(self, names: tuple[str, ...]) -> dict[str, str]:
        """
        :param names: Objects git names, such as ``<commit>:<path>`` for a file.
        :return: The text of each, as :meth:`run` of ``git show`` prints it.
        :raises GitCommandFailed: If git fails or has no object of one of the names.
        """
        texts = self.existing_object_texts(names)
        missing = [name for name in names if name not in texts]
        if missing:
            raise GitCommandFailed(
                status=0,
                detail=f"{missing[0]} {ObjectHeaderStatus.MISSING}",
                arguments=ObjectStream.arguments,
            )
        return texts

    def existing_object_texts(self, names: tuple[str, ...]) -> dict[str, str]:
        """
        :param names: Objects git names, such as ``<commit>:<path>`` for a file.
        :return: The text of each that exists, as :meth:`run` of ``git show`` prints
            it; a name git has no object of is left out.
        :raises GitCommandFailed: If git fails or answers a name ambiguously.
        """
        texts: dict[str, str] = {}
        for name in names:
            content = self.object_stream.content(name)
            if content is not None:
                text = content.decode(GIT_TEXT_ENCODING)
                texts[name] = text.replace("\r\n", "\n").replace("\r", "\n").strip()
        return texts

    @cached_property
    def object_stream(self) -> ObjectStream:
        """
        The objects of this checkout, read through one ``git cat-file`` kept running.
        """
        return ObjectStream(self.working_directory)

    def commit_files(
        self,
        parent: str | None,
        files: Mapping[str, str | None],
        message: str,
        merged_parents: tuple[str, ...] = (),
        date: str | None = None,
        copied: Mapping[str, str] | None = None,
    ) -> str:
        """
        Commit files on top of a commit without touching the working tree or the index,
        keeping every file of the parent not given.

        :param parent: The commit to build on, ``None`` for a commit with no parent.
        :param files: What to write, by path, each without its final newline;
            ``None`` removes the file.
        :param message: The commit message.
        :param merged_parents: Further parents after *parent*, whose files the commit
            does not keep.
        :param date: The commit's author and committer date, the clock's when ``None``.
        :param copied: Files to take byte for byte, mode included, from another
            commit: that commit by each file's path there and here.
        :return: The new commit.
        """
        with tempfile.TemporaryDirectory() as scratch:
            index = {
                GitVariable.INDEX_FILE: (
                    Path(scratch) / CommitScratchFile.INDEX
                ).as_posix()
            }
            self.run("read-tree", parent or "--empty", environment=index)
            for path, commit in (copied or {}).items():
                mode, _, blob = self.run("ls-tree", commit, "--", path).split()[:3]
                self.run(
                    "update-index",
                    "--add",
                    "--cacheinfo",
                    f"{mode},{blob},{path}",
                    environment=index,
                )
            blob_file = Path(scratch) / CommitScratchFile.BLOB
            for path, text in files.items():
                if text is None:
                    self.run("update-index", "--force-remove", path, environment=index)
                    continue
                blob_file.write_bytes(f"{text}\n".encode(GIT_TEXT_ENCODING))
                blob = self.run("hash-object", "-w", str(blob_file))
                self.run(
                    "update-index",
                    "--add",
                    "--cacheinfo",
                    f"100644,{blob},{path}",
                    environment=index,
                )
            tree = self.run("write-tree", environment=index)
        parents = tuple(commit for commit in (parent, *merged_parents) if commit)
        return self.commit_tree(tree, parents, message, date)

    def commit_tree(
        self,
        tree: str,
        parents: tuple[str, ...],
        message: str,
        date: str | None = None,
    ) -> str:
        """
        Record a tree as a commit without touching any branch.

        :param tree: The tree the commit records.
        :param parents: Its parents, its first parent first.
        :param message: The commit message.
        :param date: The commit's author and committer date, the clock's when ``None``.
        :return: The new commit.
        """
        dates = (
            {}
            if date is None
            else {GitVariable.AUTHOR_DATE: date, GitVariable.COMMITTER_DATE: date}
        )
        parent_arguments = [
            argument for commit in parents for argument in ("-p", commit)
        ]
        return self.run(
            "commit-tree", tree, *parent_arguments, "-m", message, environment=dates
        )

    def parents_of(self, commit: str) -> tuple[str, ...]:
        """:param commit: Any reference git can resolve to a commit.
        :return: The commit's parents, its first parent first."""
        return tuple(
            self.run("rev-list", "--parents", "--max-count=1", commit).split()[1:]
        )

    def tree_of(self, commit: str) -> str:
        """:param commit: Any reference git can resolve to a commit.
        :return: The tree the commit records."""
        return self.run("rev-parse", f"{commit}^{{tree}}")

    def automatic_merge_tree(self, first: str, second: str) -> str | None:
        """
        Merge two commits without touching any branch or the working tree.

        :param first: One side of the merge.
        :param second: The other side.
        :return: The tree merging them produces, or ``None`` when it conflicts.
        """
        merge = self.attempt("merge-tree", "--write-tree", first, second)
        return merge.output.splitlines()[0] if merge.succeeded else None

    def merge_commit(self, first: str, second: str, message: str) -> MergeCommit:
        """
        Merge two commits into a new commit, keeping the merge's conflicts in its files.

        :param first: The merge's first parent.
        :param second: Its second parent.
        :param message: The commit message.
        :return: The merge commit and the files it conflicts on.
        :raises GitCommandFailed: If git fails for any reason other than a conflict.
        """
        merge = self.attempt(
            "merge-tree",
            "--write-tree",
            "--name-only",
            "--no-messages",
            "-z",
            first,
            second,
        )
        if merge.exit_status != MERGE_CONFLICT_EXIT_STATUS:
            merge.raise_if_failed()
        tree, *conflicted_paths = merge.output.split("\0")
        return MergeCommit(
            self.run("commit-tree", tree, "-p", first, "-p", second, "-m", message),
            frozenset(PurePosixPath(path) for path in conflicted_paths if path),
        )

    def adds_only_merges(self, candidate: str, *references: str) -> bool:
        """:param candidate: The reference whose history is examined.
        :param references: The references it is compared against.
        :return: Whether every commit *candidate* holds beyond all of *references* is a
            merge.
        :raises UnresolvableReferenceError: If any reference names no commit here.
        """
        for compared in (*references, candidate):
            if not self.attempt(
                "rev-parse", "--verify", "--quiet", f"{compared}^{{commit}}"
            ).succeeded:
                raise UnresolvableReferenceError(reference=compared)
        beyond = self.run(
            "rev-list",
            "--no-merges",
            "--max-count=1",
            candidate,
            *(f"^{reference}" for reference in references),
        )
        return not beyond

    def checkout(self, branch: str, start_point: str) -> None:
        """
        Put a branch at a starting point and check it out.

        :param branch: The branch to move and check out.
        :param start_point: What to point it at.
        """
        self.run("checkout", "--quiet", "-B", branch, start_point)

    def checked_out_branch(self) -> str:
        """:return: The branch whose content a push would move."""
        return self.run("branch", "--show-current")

    def merge(self, reference: str, message: str) -> GitCommandResult:
        """:param reference: The reference to merge in.
        :param message: The merge commit's message.
        :return: The finished merge, whose failure is a conflict only when it left
            unmerged paths behind."""
        return self.attempt("merge", "--no-edit", "--message", message, reference)

    def trailer_value(self, commit: str, trailer: CommitTrailer) -> str:
        """:param commit: Any reference git can resolve to a commit.
        :param trailer: The trailer key read.
        :return: The value the commit's message gives that trailer, empty when it has
            none."""
        return self.run(
            "log",
            "--max-count=1",
            f"--format=%(trailers:key={trailer},valueonly)",
            commit,
        )

    def rebase(self, reference: str) -> GitCommandResult:
        """:param reference: The reference to rebase onto.
        :return: The finished rebase, whose failure is a conflict only when it left
            unmerged paths behind."""
        return self.attempt("rebase", reference)

    def abandon(self, strategy: IntegrationStrategy) -> None:
        """
        Undo whichever integration just failed.

        :param strategy: The integration that was attempted.
        """
        self.attempt(
            "rebase" if strategy is IntegrationStrategy.REBASE else "merge", "--abort"
        )

    def unmerged_paths(self) -> tuple[str, ...]:
        """:return: The paths the integration that just failed left conflicted."""
        unmerged = self.attempt("diff", "--name-only", "--diff-filter=U")
        return tuple(path for path in unmerged.output.splitlines() if path)

    def push(self, proposed: ProposedPush) -> GitCommandResult:
        """
        Publish a refspec, forcing only where the push itself says it is authorised.

        :param proposed: What to publish, and whether a rewrite is authorised.
        :return: The finished push, whose failure the caller reports rather than forces.
        """
        lease = ["--force-with-lease"] if proposed.with_lease else []
        return self.attempt(
            "push", "--quiet", *lease, proposed.remote, proposed.refspec
        )

    def contains(self, candidate: str, descendant: str) -> bool:
        """:param candidate: The reference that may be contained.
        :param descendant: The reference that may contain it.
        :return: Whether *candidate* is an ancestor of *descendant*."""
        return self.attempt(
            "merge-base", "--is-ancestor", candidate, descendant
        ).succeeded

    def share_history(self, first: str, second: str) -> bool:
        """
        :param first: Any reference git can resolve to a commit.
        :param second: Another one.
        :return: Whether the two commits have a common ancestor.
        """
        return self.attempt("merge-base", first, second).succeeded

    def merge_base(self, first: str, second: str) -> str:
        """
        :param first: Any reference git can resolve to a commit.
        :param second: Another one.
        :return: The best common ancestor of the two commits.
        """
        return self.run("merge-base", first, second)


@dataclass(frozen=True)
class TransientGitSetting:
    """
    A git config setting in force for the processes given it, written to no config file
    and taking precedence over every one.
    """

    key: str
    """
    The setting's key, such as ``user.name``.
    """
    value: str
    """
    The value it takes.
    """

    def variables(self, environment: Mapping[str, str]) -> dict[str, str]:
        """
        :param environment: The environment the setting is added to, whose own
            transient settings stay in force.
        :return: The variables that add it, to be merged over *environment*.
        """
        index = int(environment.get(GitVariable.CONFIGURATION_COUNT) or 0)
        return {
            GitVariable.CONFIGURATION_COUNT: str(index + 1),
            f"{GitVariable.CONFIGURATION_KEY_PREFIX}{index}": self.key,
            f"{GitVariable.CONFIGURATION_VALUE_PREFIX}{index}": self.value,
        }


# %% commit trailers


class CommitTrailer(StrEnum):
    """
    The trailer keys basstler writes into the commits it makes, and later recognises
    those commits by.
    """

    RESTACKED_PARENT = "Restacked-parent"
    """
    Names the parent a restack merged in, marking the merge as the restack's own rather
    than one a person made.
    """
    RESTACKED_PARENT_COMMIT = "Restacked-parent-commit"
    """
    The commit of the parent a restack merged in, which a restack's own merge records as
    its second parent.
    """
    ACTION_REQUEST = "Basstler-request"
    """
    The identifier of the upstream-reviews request whose branch the commit is on,
    marking the branch as basstler's own rather than one a person made.
    """


# %% integrating a moved parent


class IntegrationStrategy(StrEnum):
    """
    How a branch integrates its parent's moved tip during a restack.
    """

    MERGE = "merge"
    """
    Merge the parent's tip in, replacing the merges earlier restacks left that only
    brought in an older state of the parent, so the branch carries one such merge.
    """

    REBASE = "rebase"
    """
    Replay the branch onto the parent's tip, which rewrites published history and is
    authorised only by the branch's own rebase label.
    """
