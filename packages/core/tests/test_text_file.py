"""
Tests for :mod:`basstler.text_file`: text read and written as UTF-8 whatever the locale
encoding.
"""

from __future__ import annotations

from pathlib import Path

from basstler.text_file import UTF_8, TextFile

from basstler_testing.constants.paths import TextFileSnippet

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
