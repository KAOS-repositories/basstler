"""
Judging Markdown documentation, whose python code blocks are compared as code and the
rest as prose.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from basstler.class_property import classproperty
from basstler.review_triage.comparison import (
    ChangeKind,
    ChangeKinds,
    ContentComparison,
    FileSuffix,
    JudgmentContext,
    ProseComparison,
    PythonComparison,
)
from basstler.review_triage.keyword_arguments import KeywordArgumentComparison
from basstler.review_triage.markdown_document import CODE_BLOCK
from basstler.review_triage.python_source import PythonSource

# %% splitting a document

CODE_BLOCK_PLACEHOLDER = "\0code block\0"
"""
What stands for a code block in the prose around it.
"""


@dataclass(frozen=True)
class SplitMarkdown:
    """
    A Markdown document in its python code blocks and the prose around them.
    """

    prose: str
    """
    The document with each python code block replaced by :data:`CODE_BLOCK_PLACEHOLDER`.
    """

    code_blocks: tuple[str, ...]
    """
    The content of each python code block, in document order.
    """

    @classmethod
    def from_text(cls, text: str) -> SplitMarkdown:
        """
        :param text: A Markdown document.
        :return: It split into its python code blocks and the prose around them.
        """
        return cls(
            CODE_BLOCK.sub(CODE_BLOCK_PLACEHOLDER, text),
            tuple(match["code"] for match in CODE_BLOCK.finditer(text)),
        )


# %% the judgment


@dataclass(frozen=True)
class MarkdownComparison(ContentComparison):
    """
    Compares Markdown by its python code blocks as code and the rest as prose.
    """

    code: PythonComparison = field(default_factory=KeywordArgumentComparison)
    """
    How the code blocks are compared.
    """

    prose: ProseComparison = field(default_factory=ProseComparison)
    """
    How the text around the code blocks is compared.
    """

    @classproperty
    def suffixes(cls) -> frozenset[str]:
        return frozenset({FileSuffix.MARKDOWN})

    def text_changes(
        self, base_text: str, head_text: str, context: JudgmentContext
    ) -> ChangeKinds | None:
        base = SplitMarkdown.from_text(base_text)
        head = SplitMarkdown.from_text(head_text)
        if len(base.code_blocks) != len(head.code_blocks):
            return None
        kinds = self.prose.text_changes(base.prose, head.prose, context)
        if kinds is None:
            return None
        kinds = set(kinds)
        for base_block, head_block in zip(
            base.code_blocks, head.code_blocks, strict=True
        ):
            block_kinds = self.block_changes(base_block, head_block, context)
            if block_kinds is None:
                return None
            kinds |= block_kinds
        return frozenset(kinds)

    def block_changes(
        self, base_block: str, head_block: str, context: JudgmentContext
    ) -> ChangeKinds | None:
        """
        :param base_block: A code block's content in the base commit.
        :param head_block: The same block's content in the head commit.
        :param context: What the judgment may consult about the pull request.
        :return: What the change consists of, ``None`` when it is not provably
            mechanical.
        """
        if base_block == head_block:
            return ChangeKind.no_change
        base = PythonSource.from_text(base_block)
        head = PythonSource.from_text(head_block)
        if not (base.parses and head.parses):
            return None
        return self.code.source_changes(base, head, context)
