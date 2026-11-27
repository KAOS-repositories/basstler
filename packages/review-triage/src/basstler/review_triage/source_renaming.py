"""
A Python file's text with a pull request's renames applied where the triage applies
them: identifiers, imported module paths, documentation strings and comments, never
other string literals.
"""

from __future__ import annotations

import ast
import io
import tokenize
from dataclasses import dataclass
from functools import cached_property

from basstler.review_triage.python_source import FUTURE_MODULE, PythonSource
from basstler.review_triage.renames import DOTTED_NAME_SEPARATOR, RenameMap

# %% one replaced piece of text


@dataclass(frozen=True)
class TextReplacement:
    """
    Text replacing the characters between two positions of a file.
    """

    start: tuple[int, int]
    """
    The line, counted from one, and the column of the first character replaced.
    """

    end: tuple[int, int]
    """
    The line and the column right after the last character replaced.
    """

    text: str
    """
    What replaces them.
    """


# %% the renamed text


@dataclass(frozen=True)
class SourceRenaming:
    """
    One version of a Python file renamed by a pull request's renames, everything else
    kept as written.
    """

    source: PythonSource
    """
    The file's version.
    """

    renames: RenameMap
    """
    The renames to apply.
    """

    @cached_property
    def tokens(self) -> tuple[tokenize.TokenInfo, ...]:
        """
        The file's tokens, in order.
        """
        return tuple(tokenize.generate_tokens(io.StringIO(self.source.text).readline))

    @cached_property
    def documentation_starts(self) -> frozenset[tuple[int, int]]:
        """
        Where each documentation string of the file starts.
        """
        return frozenset(
            (node.value.lineno, node.value.col_offset)
            for node in ast.walk(self.source.tree)
            if isinstance(node, ast.stmt) and PythonSource.is_documentation(node)
        )

    @cached_property
    def import_lines(self) -> frozenset[int]:
        """
        The lines of the file's import statements, other than those of ``__future__``.
        """
        return frozenset(
            line
            for node in ast.walk(self.source.tree)
            if isinstance(node, ast.Import)
            or (isinstance(node, ast.ImportFrom) and node.module != FUTURE_MODULE)
            for line in range(node.lineno, (node.end_lineno or node.lineno) + 1)
        )

    def renamed_text(self) -> str:
        """
        :return: The file's text with every identifier, imported module path,
            documentation string and comment the renames rename replaced.
        """
        lines = self.source.text.splitlines(keepends=True)
        for replacement in reversed(self.replacements()):
            (first_line, first_column), (last_line, end_column) = (
                replacement.start,
                replacement.end,
            )
            before = lines[first_line - 1][:first_column]
            after = lines[last_line - 1][end_column:]
            lines[first_line - 1 : last_line] = [before + replacement.text + after]
        return "".join(lines)

    def replacements(self) -> list[TextReplacement]:
        """
        :return: What the renames replace, in the order it occurs in the file.
        """
        replacements: list[TextReplacement] = []
        tokens = self.tokens
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if token.type == tokenize.NAME and token.start[0] in self.import_lines:
                end = self.dotted_path_end(index)
                path = "".join(each.string for each in tokens[index:end])
                renamed = self.renames.renamed_identifier(path)
                if renamed != path:
                    replacements.append(
                        TextReplacement(token.start, tokens[end - 1].end, renamed)
                    )
                index = end
                continue
            renamed = self.renamed_token(token)
            if renamed != token.string:
                replacements.append(TextReplacement(token.start, token.end, renamed))
            index += 1
        return replacements

    def renamed_token(self, token: tokenize.TokenInfo) -> str:
        """
        :param token: A token outside the file's import statements.
        :return: Its text once renamed.
        """
        if token.type == tokenize.NAME and PythonSource.is_identifier(token):
            return self.renames.replacements.get(token.string, token.string)
        if token.type == tokenize.COMMENT or (
            token.type == tokenize.STRING and token.start in self.documentation_starts
        ):
            return self.renames.renamed_prose(token.string)
        return token.string

    def dotted_path_end(self, index: int) -> int:
        """
        :param index: The index of a name token in :attr:`tokens`.
        :return: The index right after the dotted path it starts.
        """
        tokens = self.tokens
        end = index + 1
        while (
            end + 1 < len(tokens)
            and tokens[end].string == DOTTED_NAME_SEPARATOR
            and tokens[end + 1].type == tokenize.NAME
        ):
            end += 2
        return end
