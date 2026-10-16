"""Tokenizers that report where each token sits in the text, so chunks can be cut by tokens."""

import re
from typing import Protocol


class Tokenizer(Protocol):
    def token_spans(self, text: str) -> list[tuple[int, int]]:
        """Return the [start, end) character span of every token, without special tokens."""
        ...


class WhitespaceTokenizer:
    """One token per run of non-whitespace characters.

    Not what any embedding model sees, but deterministic and countable by hand, which is
    what the chunker tests need.
    """

    _TOKEN = re.compile(r"\S+")

    def token_spans(self, text: str) -> list[tuple[int, int]]:
        return [match.span() for match in self._TOKEN.finditer(text)]
