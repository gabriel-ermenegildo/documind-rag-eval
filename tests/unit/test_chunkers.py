import random

import pytest

from documind.ingestion.chunkers import FixedSizeChunker, page_range
from documind.ingestion.parser import assemble_document
from documind.ingestion.tokenization import WhitespaceTokenizer

# Ten one-letter tokens: token i spans characters [2i, 2i + 1).
TEN_TOKENS = "a b c d e f g h i j"


def fixed(size, overlap):
    return FixedSizeChunker(WhitespaceTokenizer(), size=size, overlap=overlap)


def test_windows_of_four_with_overlap_one_computed_by_hand():
    chunks = fixed(4, 1).chunk(assemble_document([TEN_TOKENS]))

    # Tokens 0-3, 3-6 and 6-9; the last window reaches token 9, so no fourth window.
    assert [(c.char_start, c.char_end) for c in chunks] == [(0, 7), (6, 13), (12, 19)]
    assert [c.content for c in chunks] == ["a b c d", "d e f g", "g h i j"]
    assert [c.index for c in chunks] == [0, 1, 2]
    assert [c.token_count for c in chunks] == [4, 4, 4]


def test_windows_of_four_with_overlap_two_do_not_repeat_the_tail():
    chunks = fixed(4, 2).chunk(assemble_document([TEN_TOKENS]))

    # Tokens 0-3, 2-5, 4-7, 6-9. A window starting at token 8 would only repeat "i j".
    assert [c.content for c in chunks] == ["a b c d", "c d e f", "e f g h", "g h i j"]


def test_last_window_is_shorter_when_tokens_do_not_divide_evenly():
    chunks = fixed(4, 1).chunk(assemble_document([TEN_TOKENS + " k"]))

    assert [c.content for c in chunks] == ["a b c d", "d e f g", "g h i j", "j k"]
    assert chunks[-1].token_count == 2


def test_document_shorter_than_one_window_is_a_single_chunk():
    chunks = fixed(512, 64).chunk(assemble_document(["Art. 5º Todos são iguais"]))

    assert len(chunks) == 1
    assert chunks[0].content == "Art. 5º Todos são iguais"
    assert chunks[0].token_count == 5


def test_chunk_crossing_a_page_boundary_records_both_pages():
    # "a b c" is page 1 at [0, 5); "d e f" is page 2 at [7, 12).
    document = assemble_document(["a b c", "d e f"])

    chunks = fixed(4, 1).chunk(document)

    assert [(c.content, c.page_start, c.page_end) for c in chunks] == [
        ("a b c\n\nd", 1, 2),
        ("d e f", 2, 2),
    ]


def test_document_without_tokens_has_no_chunks():
    assert fixed(4, 1).chunk(assemble_document([])) == []
    assert fixed(4, 1).chunk(assemble_document([" ", ""])) == []


def test_invariants_hold_on_a_longer_multi_page_document():
    rng = random.Random(42)
    words = ["prazo", "titular", "dados", "art.", "§", "1º", "controlador", "ação"]
    pages = [" ".join(rng.choices(words, k=rng.randint(0, 120))) for _ in range(12)]
    document = assemble_document(pages)
    tokens = WhitespaceTokenizer().token_spans(document.text)
    size, overlap = 50, 10

    chunks = fixed(size, overlap).chunk(document)

    covered = set()
    for chunk in chunks:
        assert chunk.content == document.text[chunk.char_start : chunk.char_end]
        assert 1 <= chunk.token_count <= size
        assert chunk.page_start <= chunk.page_end
        in_chunk = [
            i for i, (s, e) in enumerate(tokens) if chunk.char_start <= s and e <= chunk.char_end
        ]
        assert len(in_chunk) == chunk.token_count
        covered.update(in_chunk)
    # No text is lost: every token of the document is in at least one chunk.
    assert covered == set(range(len(tokens)))
    # Consecutive chunks share exactly `overlap` tokens.
    for previous, current in zip(chunks, chunks[1:], strict=False):
        shared = [s for s, e in tokens if current.char_start <= s and e <= previous.char_end]
        assert len(shared) == overlap


def test_strategy_name_encodes_size_and_overlap():
    assert fixed(512, 64).strategy == "fixed_512_64"


@pytest.mark.parametrize(
    ("size", "overlap"),
    [(0, 0), (-1, 0), (4, 4), (4, 5), (4, -1)],
)
def test_invalid_size_or_overlap_is_rejected(size, overlap):
    with pytest.raises(ValueError):
        fixed(size, overlap)


# Pages "A" at [0, 1), blank at [3, 3), "B" at [5, 6); separators at [1, 3) and [3, 5).
PAGES_WITH_BLANK = assemble_document(["A", "", "B"]).pages


@pytest.mark.parametrize(
    ("char_start", "char_end", "expected"),
    [
        (0, 1, (1, 1)),  # exactly page 1
        (0, 6, (1, 3)),  # whole document: the blank page is inside the range
        (2, 6, (3, 3)),  # starts in a separator: goes to the next page with text
        (0, 4, (1, 1)),  # ends in a separator: goes back to the previous page with text
    ],
)
def test_page_range_skips_separators_and_blank_pages(char_start, char_end, expected):
    assert page_range(PAGES_WITH_BLANK, char_start, char_end) == expected


def test_page_range_rejects_a_span_with_no_page_text():
    with pytest.raises(ValueError, match="does not overlap"):
        page_range(PAGES_WITH_BLANK, 1, 5)
