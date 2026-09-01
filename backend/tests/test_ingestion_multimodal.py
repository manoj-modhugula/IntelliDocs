import importlib.util
from pathlib import Path

from app.services.ingestion import IngestionService
from app.services.structured_extract import extract_figures, extract_tables, table_to_markdown
from app.services.storage import storage_service


def _pdf_bytes():
    path = Path(__file__).resolve().parent.parent / "scripts/evaluation/build_multimodal_pdf.py"
    spec = importlib.util.spec_from_file_location("build_multimodal_pdf", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.build_multimodal_pdf()


def test_table_to_markdown_renders_header_and_row():
    md = table_to_markdown([["SKU", "Price"], ["SKU-ACME-1", "19.99"]])
    assert "SKU-ACME-1" in md
    assert "19.99" in md
    assert md.splitlines()[1].startswith("| ---")


def test_extract_table_has_bbox(tmp_path, monkeypatch):
    monkeypatch.setattr(storage_service, "local_dir", tmp_path)
    tables = extract_tables(_pdf_bytes(), "doc-mm")
    assert len(tables) >= 1
    table = tables[0]
    assert table["chunk_type"] == "table"
    assert "SKU-ACME-1" in table["content"]
    assert all(table[k] is not None for k in ("bbox_x0", "bbox_y0", "bbox_x1", "bbox_y1"))
    assert table["bbox_x1"] > table["bbox_x0"]
    assert table["bbox_y1"] > table["bbox_y0"]


def test_extract_figure_writes_png(tmp_path, monkeypatch):
    monkeypatch.setattr(storage_service, "local_dir", tmp_path)
    figures = extract_figures(_pdf_bytes(), "doc-mm")
    assert len(figures) >= 1
    fig = figures[0]
    assert fig["chunk_type"] == "figure"
    assert "FIG-PUMP-07" in (fig.get("caption") or "") + fig["content"]
    key = fig["image_key"]
    assert key
    assert (tmp_path / key).exists()
    assert (tmp_path / key).stat().st_size > 20


def test_selective_embedding_never_skips_tables():
    svc = IngestionService()
    chunks = [
        {"content": "x" * 20, "token_count": 5, "chunk_type": "text"},
        {"content": "| SKU | Price |\n| --- | --- |\n| A | 1 |", "token_count": 12, "chunk_type": "table"},
        {"content": "[Figure] pump", "token_count": 4, "chunk_type": "figure"},
    ]
    selected, skipped = svc._select_chunks_for_embedding(chunks)
    types = {c["chunk_type"] for c in selected}
    assert "table" in types
    assert "figure" in types
    assert all(c.get("chunk_type") not in ("table", "figure") for c in skipped)


def test_prune_keeps_short_table_chunks():
    svc = IngestionService()
    chunks = [
        {"content": "| A | B |", "token_count": 2, "chunk_type": "table"},
        {"content": "tiny", "token_count": 1, "chunk_type": "text"},
    ]
    pruned = svc._prune_chunks(chunks)
    assert any(c["chunk_type"] == "table" for c in pruned)
