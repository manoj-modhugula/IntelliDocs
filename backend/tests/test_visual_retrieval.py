from app.models import Chunk
from app.services.retrieval import RetrievalService, query_wants_visual


def test_query_wants_visual_for_figures_only():
    assert query_wants_visual("What does FIG-PUMP-07 show?") is True
    assert query_wants_visual("Describe the pump diagram") is True
    assert query_wants_visual("How long does site 12 retain logs?") is False
    assert query_wants_visual("What is the price of SKU-N003?") is False


def test_identifier_regex_does_not_match_word_figure():
    from app.services.retrieval import _IDENT

    assert _IDENT.search("figure") is None
    assert _IDENT.search("FIG-UNIT-024")
    assert _IDENT.search("SKU-N003")
    assert _IDENT.search("site 12")


def test_rrf_merge_includes_clip_list():
    text = Chunk(id="t1", document_id="d", content="refund window 14 days", chunk_index=0)
    fig = Chunk(
        id="f1",
        document_id="d",
        content="[Figure] FIG-PUMP-07 centrifugal pump",
        chunk_index=1,
        chunk_type="figure",
    )
    svc = RetrievalService()
    semantic = [(text, 0.9)]
    bm25 = [(text, 0.8)]
    visual = [(fig, 0.95)]
    merged = svc._rrf_merge_lists([semantic, bm25, visual], top_k=5)
    ids = [c.id for c, _ in merged]
    assert "t1" in ids
    assert "f1" in ids
    assert merged[0][0].id == "t1"


def test_rrf_empty_visual_does_not_change_text_winner():
    a = Chunk(id="a", document_id="d", content="alpha", chunk_index=0)
    b = Chunk(id="b", document_id="d", content="beta", chunk_index=1)
    svc = RetrievalService()
    with_empty = svc._rrf_merge_lists([[(a, 1.0), (b, 0.5)], [(a, 0.8)], []], top_k=2)
    without = svc._rrf_merge_lists([[(a, 1.0), (b, 0.5)], [(a, 0.8)]], top_k=2)
    assert [c.id for c, _ in with_empty] == [c.id for c, _ in without]
