"""PDF parsing: turns PDF bytes into page texts with offsets into the full document text."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import pymupdf

# Joins page texts into the full document text. Offsets of pages and chunks refer to that text.
PAGE_SEPARATOR = "\n\n"

# PyMuPDF's default for plain text, minus ligature preservation: "ﬁ" comes out as "fi",
# so quotes typed by a person or an LLM can match the text. No Unicode normalization
# beyond that: NFKC would turn the ordinal "º" of "Art. 5º" into a plain "o".
TEXT_FLAGS = pymupdf.TEXTFLAGS_TEXT & ~pymupdf.TEXT_PRESERVE_LIGATURES


class ParserError(Exception):
    """The PDF cannot be turned into text. The message is shown to the user as the reason."""


class InvalidPdfError(ParserError):
    """The bytes are not a readable PDF."""


class NoTextLayerError(ParserError):
    """The PDF has no extractable text, typically a scanned document."""


@dataclass(frozen=True)
class ParsedPage:
    number: int  # 1-based, as shown by PDF viewers
    text: str
    # Offsets into ParsedDocument.text: text == document.text[char_start:char_end].
    char_start: int
    char_end: int


@dataclass(frozen=True)
class ParsedDocument:
    text: str
    pages: tuple[ParsedPage, ...]
    title: str | None

    @property
    def num_pages(self) -> int:
        return len(self.pages)


class Parser(Protocol):
    def parse(self, data: bytes) -> ParsedDocument: ...


def assemble_document(page_texts: Sequence[str], title: str | None = None) -> ParsedDocument:
    """Join page texts with PAGE_SEPARATOR and record where each page starts and ends."""
    pages = []
    cursor = 0
    for number, text in enumerate(page_texts, start=1):
        if number > 1:
            cursor += len(PAGE_SEPARATOR)
        pages.append(ParsedPage(number, text, cursor, cursor + len(text)))
        cursor += len(text)
    return ParsedDocument(PAGE_SEPARATOR.join(page_texts), tuple(pages), title)


class PyMuPdfParser:
    """Extracts the text layer of a PDF with PyMuPDF. Scanned PDFs are rejected (no OCR)."""

    def parse(self, data: bytes) -> ParsedDocument:
        try:
            pdf = pymupdf.open(stream=data, filetype="pdf")
        except pymupdf.FileDataError as exc:
            raise InvalidPdfError("File is not a readable PDF.") from exc

        with pdf:
            if pdf.needs_pass:
                raise InvalidPdfError("PDF is password-protected.")
            page_texts = [page.get_text("text", flags=TEXT_FLAGS).strip() for page in pdf]
            title = (pdf.metadata or {}).get("title", "").strip() or None

        document = assemble_document(page_texts, title)
        if not document.text.strip():
            raise NoTextLayerError(
                "PDF has no text layer (scanned document?). OCR is not supported."
            )
        return document
