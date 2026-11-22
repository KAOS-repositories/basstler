"""
The Claude Code tools a session calls, by the names Claude Code gives them.
"""

from __future__ import annotations

from enum import StrEnum


class SessionTool(StrEnum):
    """
    The Claude Code tools a session calls.
    """

    # %% built-in tools

    RUN_SHELL_COMMAND = "Bash"
    """
    Runs a command in the session's shell.
    """

    READ_FILE = "Read"
    """
    Reads a file.
    """

    WRITE_FILE = "Write"
    """
    Writes a whole file.
    """

    EDIT_FILE = "Edit"
    """
    Replaces text in a file.
    """

    SEARCH_FILE_CONTENTS = "Grep"
    """
    Searches the contents of files.
    """

    FIND_FILES = "Glob"
    """
    Finds files by name.
    """

    ASK_USER = "AskUserQuestion"
    """
    Asks the user to choose between options.
    """

    RUN_SKILL = "Skill"
    """
    Loads another skill's instructions.
    """

    ENTER_PLAN_MODE = "EnterPlanMode"
    """
    Switches the session to presenting a plan before changing anything.
    """

    EXIT_PLAN_MODE = "ExitPlanMode"
    """
    Presents the plan for the user's approval.
    """

    # %% GitHub tools

    READ_GITHUB_USER = "mcp__github__get_me"
    """
    Reads the signed-in GitHub user.
    """

    READ_LABEL = "mcp__github__get_label"
    """
    Reads one label of a repository.
    """

    READ_REPOSITORY_FILE = "mcp__github__get_file_contents"
    """
    Reads a file or directory of a repository on GitHub.
    """

    READ_ISSUE = "mcp__github__issue_read"
    """
    Reads an issue and its comments.
    """

    WRITE_ISSUE = "mcp__github__issue_write"
    """
    Creates or updates an issue.
    """

    LIST_PULL_REQUESTS = "mcp__github__list_pull_requests"
    """
    Lists a repository's pull requests.
    """

    READ_PULL_REQUEST = "mcp__github__pull_request_read"
    """
    Reads a pull request, its diff, checks or review threads.
    """

    CREATE_PULL_REQUEST = "mcp__github__create_pull_request"
    """
    Opens a pull request.
    """

    UPDATE_PULL_REQUEST = "mcp__github__update_pull_request"
    """
    Changes a pull request's title, description, base or draft state.
    """

    LIST_ACTIONS = "mcp__github__actions_list"
    """
    Lists a repository's workflows, runs or jobs.
    """

    READ_JOB_LOGS = "mcp__github__get_job_logs"
    """
    Reads the logs of a workflow job.
    """

    # %% cloud session tools

    ATTACH_REPOSITORY = "mcp__claude-code-remote__add_repo"
    """
    Attaches a repository to a cloud session, which lets its proxy answer that
    repository's git and API requests.
    """

    REGISTER_REPOSITORY_ROOT = "mcp__claude-code-remote__register_repo_root"
    """
    Loads the instructions of an attached repository's local clone into the session.
    """

    SUBSCRIBE_PULL_REQUEST_ACTIVITY = "mcp__claude-code-remote__subscribe_pr_activity"
    """
    Delivers a pull request's comments, reviews and checks into the session.
    """

    CREATE_SESSION = "mcp__claude-code-remote__create_session"
    """
    Starts another cloud session.
    """

    READ_SESSION = "mcp__claude-code-remote__get_session"
    """
    Reads another cloud session's state.
    """

    LIST_SESSION_EVENTS = "mcp__claude-code-remote__list_events"
    """
    Reads another cloud session's transcript.
    """

    ARCHIVE_SESSION = "mcp__claude-code-remote__archive_session"
    """
    Archives a cloud session and releases its container.
    """
