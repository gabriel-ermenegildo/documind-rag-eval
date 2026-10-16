"""Chunking strategies: split a parsed document into chunks that keep pages and offsets."""

from bisect import bisect_left, bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from documind.ingestion.parser import ParsedDocument, ParsedPage
from documind.ingestion.tokenization import Tokenizer


@dataclass(frozen=True)
class ChunkDraft:
    """A chunk before it is embedded and stored. content == document.text[char_start:char_end]."""

    index: int
    content: str
    page_start: int
    page_end: int
    char_start: int
    char_end: int
    token_count: int


class Chunker(Protocol):
    @property
    def strategy(self) -> str:
        """Name stored in chunks.chunking_strategy, e.g. "fixed_512_64"."""
        ...

    def chunk(self, document: ParsedDocument) -> list[ChunkDraft]: ...


def page_range(pages: Sequence[ParsedPage], char_start: int, char_end: int) -> tuple[int, int]:
    """Return the first and last page numbers whose text overlaps [char_start, char_end).

    Blank pages and the separators between pages hold no text, so a span that starts or
    ends inside them is attributed to the nearest page that does.
    """
    pages_with_text = [page for page in pages if page.char_end > page.char_start]
    # First page that ends after the span starts; last page that starts before the span ends.
    first = bisect_right([page.char_end for page in pages_with_text], char_start)
    last = bisect_left([page.char_start for page in pages_with_text], char_end) - 1
    if first > last:
        raise ValueError(f"Span [{char_start}, {char_end}) does not overlap any page text.")
    return pages_with_text[first].number, pages_with_text[last].number


class FixedSizeChunker:
    """Windows of `size` tokens over the whole document; consecutive windows share `overlap`.

    Windows ignore page boundaries, so a chunk may span pages (page_start != page_end).
    """

    def __init__(self, tokenizer: Tokenizer, size: int, overlap: int) -> None:
        if size <= 0:
            raise ValueError("size must be positive.")
        if not 0 <= overlap < size:
            raise ValueError("overlap must be zero or more and smaller than size.")
        self._tokenizer = tokenizer
        self._size = size
        self._overlap = overlap

    @property
    def strategy(self) -> str:
        return f"fixed_{self._size}_{self._overlap}"

    def chunk(self, document: ParsedDocument) -> list[ChunkDraft]:
        spans = self._tokenizer.token_spans(document.text)
        step = self._size - self._overlap
        chunks: list[ChunkDraft] = []
        start = 0
        while start < len(spans):
            window = spans[start : start + self._size]
            char_start, char_end = window[0][0], window[-1][1]
            page_start, page_end = page_range(document.pages, char_start, char_end)
            chunks.append(
                ChunkDraft(
                    index=len(chunks),
                    content=document.text[char_start:char_end],
                    page_start=page_start,
                    page_end=page_end,
                    char_start=char_start,
                    char_end=char_end,
                    token_count=len(window),
                )
            )
            # Stop once the last token is in a window: another one would only repeat the tail.
            if start + self._size >= len(spans):
                break
            start += step
        return chunks
