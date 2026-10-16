from documind.ingestion.tokenization import WhitespaceTokenizer


def test_whitespace_tokenizer_returns_spans_of_non_whitespace_runs():
    text = "Art. 5º\n\n  ação"

    spans = WhitespaceTokenizer().token_spans(text)

    assert spans == [(0, 4), (5, 7), (11, 15)]
    assert [text[start:end] for start, end in spans] == ["Art.", "5º", "ação"]


def test_whitespace_tokenizer_on_blank_text_returns_no_tokens():
    assert WhitespaceTokenizer().token_spans(" \n\t ") == []
