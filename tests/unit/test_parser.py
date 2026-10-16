import pymupdf
import pytest

from documind.ingestion.parser import (
    InvalidPdfError,
    NoTextLayerError,
    ParsedPage,
    PyMuPdfParser,
    assemble_document,
)


def test_assemble_document_offsets_computed_by_hand():
    document = assemble_document(["Alpha", "Beta"])

    # "Alpha" is [0, 5), the separator "\n\n" is [5, 7), "Beta" is [7, 11).
    assert document.text == "Alpha\n\nBeta"
    assert document.pages == (
        ParsedPage(number=1, text="Alpha", char_start=0, char_end=5),
        ParsedPage(number=2, text="Beta", char_start=7, char_end=11),
    )


def test_assemble_document_blank_page_keeps_numbering_and_offsets():
    document = assemble_document(["A", "", "B"])

    # "A" [0, 1), separator [1, 3), blank page [3, 3), separator [3, 5), "B" [5, 6).
    assert document.text == "A\n\n\n\nB"
    assert [(p.number, p.char_start, p.char_end) for p in document.pages] == [
        (1, 0, 1),
        (2, 3, 3),
        (3, 5, 6),
    ]


def test_assemble_document_without_pages_is_empty():
    document = assemble_document([])

    assert document.text == ""
    assert document.num_pages == 0


def test_parse_returns_each_page_and_offsets_rebuild_the_full_text(make_pdf):
    pages = ["Primeira página\ncom duas linhas", "Segunda página", "Terceira página"]

    document = PyMuPdfParser().parse(make_pdf(pages))

    assert [page.text for page in document.pages] == pages
    assert [page.number for page in document.pages] == [1, 2, 3]
    for page in document.pages:
        assert document.text[page.char_start : page.char_end] == page.text


def test_parse_preserves_portuguese_characters(make_pdf):
    text = "Art. 5º, § 2º: ação e informação"

    document = PyMuPdfParser().parse(make_pdf([text]))

    assert document.text == text


def test_parse_expands_ligatures():
    # insert_text cannot draw the "ﬁ" ligature, so this PDF is built with a TextWriter.
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        writer = pymupdf.TextWriter(page.rect)
        writer.append((72, 72), "ﬁm", font=pymupdf.Font("helv"))
        writer.write_text(page)
        data = pdf.tobytes()

    assert PyMuPdfParser().parse(data).text == "fim"


def test_parse_keeps_blank_pages_in_the_numbering(make_pdf):
    document = PyMuPdfParser().parse(make_pdf(["Antes", "", "Depois"]))

    assert document.num_pages == 3
    assert [page.text for page in document.pages] == ["Antes", "", "Depois"]


def test_parse_reads_the_title_from_metadata(make_pdf):
    assert PyMuPdfParser().parse(make_pdf(["texto"], title="Lei de Teste")).title == (
        "Lei de Teste"
    )
    assert PyMuPdfParser().parse(make_pdf(["texto"])).title is None


def test_pdf_without_text_layer_fails_with_a_clear_message(make_scanned_pdf):
    with pytest.raises(NoTextLayerError, match="no text layer"):
        PyMuPdfParser().parse(make_scanned_pdf())


def test_pdf_with_only_blank_pages_has_no_text_layer(make_pdf):
    with pytest.raises(NoTextLayerError):
        PyMuPdfParser().parse(make_pdf(["", ""]))


@pytest.mark.parametrize("data", [b"not a pdf", b""], ids=["garbage", "empty"])
def test_bytes_that_are_not_a_pdf_are_rejected(data):
    with pytest.raises(InvalidPdfError, match="not a readable PDF"):
        PyMuPdfParser().parse(data)


def test_password_protected_pdf_is_rejected(make_pdf):
    with pymupdf.open(stream=make_pdf(["segredo"]), filetype="pdf") as pdf:
        encrypted = pdf.tobytes(
            encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="user", owner_pw="owner"
        )

    with pytest.raises(InvalidPdfError, match="password-protected"):
        PyMuPdfParser().parse(encrypted)
