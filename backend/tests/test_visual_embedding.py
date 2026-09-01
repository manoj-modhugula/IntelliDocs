from app.services.visual_embedding import lexical_clip_vector, VisualEmbeddingService


def _cos(a, b):
    return sum(x * y for x, y in zip(a, b))


def test_lexical_clip_shared_tokens_are_closer():
    pump = lexical_clip_vector("figure centrifugal pump diagram FIG-PUMP-07")
    query = lexical_clip_vector("pump diagram")
    other = lexical_clip_vector("refund policy table of gift cards")
    assert _cos(query, pump) > _cos(query, other)


def test_mock_embed_query_matches_caption(monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "MOCK_LLM_AND_EMBEDDINGS", True)
    svc = VisualEmbeddingService()
    q = svc.embed_query("centrifugal pump")
    img = svc.embed_image(b"", caption="Figure FIG-PUMP-07 centrifugal pump diagram")
    other = svc.embed_image(b"", caption="pricing grid SKU table")
    assert _cos(q, img) > _cos(q, other)
