"""
Tests for :mod:`basstler.text_file`: text read and written as UTF-8 whatever the locale
encoding.
"""

from __future__ import annotations

from pathlib import Path

from basstler.text_file import UTF_8, TextFile

from .constants.paths import TextFileSnippet

# %% reading and writing


def test_reading_decodes_the_file_as_utf_8():
    """
    Text no single-byte code page encodes reads back as it was written.
    """
    snippet = TextFileSnippet.NON_ASCII

    assert TextFile(snippet).read() == snippet.read_bytes().decode(UTF_8)


def test_writing_encodes_the_text_as_utf_8(tmp_path: Path):
    """
    The bytes written are the text's UTF-8 encoding.
    """
    text = TextFile(TextFileSnippet.NON_ASCII).read()
    written = tmp_path / TextFileSnippet.NON_ASCII._name_

    TextFile(written).write(text)

    assert written.read_bytes() == text.encode(UTF_8)


# %% newlines

CRLF_TEXT = "first\r\nsecond\nthird\r\n"
"""
Lines ended both ways, as a checkout with another newline setting leaves them.
"""


def test_reading_keeps_every_line_ending_as_stored(tmp_path: Path):
    """
    The text read has the line endings the file's bytes have, none translated.
    """
    stored = tmp_path / "stored.txt"
    stored.write_bytes(CRLF_TEXT.encode(UTF_8))

    assert TextFile(stored).read() == CRLF_TEXT


def test_writing_keeps_every_line_ending_as_given(tmp_path: Path):
    """
    The file gets the text's line endings, none translated.
    """
    written = tmp_path / "written.txt"

    TextFile(written).write(CRLF_TEXT)

    assert written.read_bytes() == CRLF_TEXT.encode(UTF_8)
