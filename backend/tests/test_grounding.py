from app.services.grounding import filter_answer, mock_entailed, split_claims


class _Chunk:
    def __init__(self, content, caption=None):
        self.content = content
        self.caption = caption


def test_split_claims_sentences_and_bullets():
    claims = split_claims("Refunds within 14 days. Digital cards are excluded.\n- Keep the receipt.")
    assert any("14 days" in c for c in claims)
    assert any("excluded" in c for c in claims)
    assert any("receipt" in c for c in claims)


def test_mock_entailed_keeps_supported_claim():
    evidence = "Customers may request a refund within 14 days of purchase."
    assert mock_entailed("Refunds are allowed within 14 days.", evidence) is True


def test_mock_entailed_drops_hallucination():
    evidence = "Customers may request a refund within 14 days of purchase."
    assert mock_entailed("The CEO lives on Mars.", evidence) is False


def test_filter_answer_drops_unsupported_sentence():
    chunks = [(_Chunk("Customers may request a refund within 14 days of purchase."), 1.0)]
    answer = "Refunds are allowed within 14 days. The CEO lives on Mars."
    filtered, dropped, _kept = filter_answer(answer, chunks)
    assert "14 days" in filtered
    assert "Mars" not in filtered
    assert any("Mars" in d for d in dropped)
