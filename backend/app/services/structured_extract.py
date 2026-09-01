"""Extract tables and figures from PDFs with page-geometry bounding boxes."""

from __future__ import annotations

import logging
import uuid
from io import BytesIO
from typing import List, Optional, Tuple

from app.core.config import settings
from app.services.storage import storage_service


def estimate_tokens(text: str) -> int:
    return max(len(text) // 4, 1)

logger = logging.getLogger(__name__)


def table_to_markdown(rows: List[List[Optional[str]]]) -> str:
    if not rows:
        return ""
    cleaned = [[(cell or "").replace("\n", " ").strip() for cell in row] for row in rows]
    width = max(len(r) for r in cleaned)
    for row in cleaned:
        while len(row) < width:
            row.append("")
    header = cleaned[0]
    lines = ["| " + " | ".join(header) + " |"]
    lines.append("| " + " | ".join("---" for _ in header) + " |")
    for row in cleaned[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _pdfplumber_bbox_to_pdf(page, bbox: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
    """pdfplumber (origin top-left) → PDF user space (origin bottom-left)."""
    x0, top, x1, bottom = bbox
    height = float(page.height)
    y0 = height - float(bottom)
    y1 = height - float(top)
    return float(x0), min(y0, y1), float(x1), max(y0, y1)


def _fitz_rect_to_pdf(page, rect) -> Tuple[float, float, float, float]:
    height = float(page.rect.height)
    y0 = height - float(rect.y1)
    y1 = height - float(rect.y0)
    return float(rect.x0), min(y0, y1), float(rect.x1), max(y0, y1)


def _pdf_to_fitz_rect(page, bbox: Tuple[float, float, float, float]):
    import fitz

    x0, y0, x1, y1 = bbox
    height = float(page.rect.height)
    return fitz.Rect(x0, height - y1, x1, height - y0)


def _caption_near_rect(page, rect, max_chars: int = 400) -> str:
    try:
        blocks = page.get_text("blocks") or []
    except Exception:
        return ""
    candidates = []
    for b in blocks:
        if len(b) < 5:
            continue
        bx0, by0, bx1, by1, text = b[0], b[1], b[2], b[3], (b[4] or "").strip()
        if not text:
            continue
        # directly above or below the image
        horizontally_aligned = not (bx1 < rect.x0 - 8 or bx0 > rect.x1 + 8)
        if not horizontally_aligned:
            continue
        gap_above = rect.y0 - by1
        gap_below = by0 - rect.y1
        if 0 <= gap_above <= 80:
            candidates.append((gap_above, text))
        elif 0 <= gap_below <= 80:
            candidates.append((gap_below + 0.1, text))
    candidates.sort(key=lambda x: x[0])
    if not candidates:
        return ""
    return candidates[0][1][:max_chars]


def _make_chunk(
    *,
    chunk_type: str,
    content: str,
    page_number: int,
    bbox: Tuple[float, float, float, float],
    caption: Optional[str] = None,
    image_key: Optional[str] = None,
    chunk_index: int = 0,
) -> dict:
    return {
        "content": content,
        "page_number": page_number,
        "chunk_index": chunk_index,
        "token_count": max(estimate_tokens(content), 1),
        "granularity": "structured",
        "chunk_type": chunk_type,
        "bbox_x0": bbox[0],
        "bbox_y0": bbox[1],
        "bbox_x1": bbox[2],
        "bbox_y1": bbox[3],
        "caption": caption,
        "image_key": image_key,
    }


def extract_tables(file_bytes: bytes, document_id: str) -> List[dict]:
    if not getattr(settings, "ENABLE_STRUCTURED_CHUNKS", True):
        return []
    chunks: List[dict] = []
    try:
        import pdfplumber
        import fitz
    except Exception as e:
        logger.warning("Table extract imports failed: %s", e)
        return []

    try:
        pdf = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as e:
        logger.warning("PyMuPDF open failed for table crops: %s", e)
        pdf = None

    try:
        with pdfplumber.open(BytesIO(file_bytes)) as plumber:
            for page in plumber.pages:
                try:
                    found = page.find_tables() or []
                except Exception:
                    found = []
                for table in found:
                    try:
                        rows = table.extract() or []
                    except Exception:
                        rows = []
                    md = table_to_markdown(rows)
                    if md.count("|") < 4 or not any(
                        (cell or "").strip() for row in rows for cell in (row or [])
                    ):
                        try:
                            crop = page.within_bbox(table.bbox)
                            raw = (crop.extract_text() or "").strip()
                        except Exception:
                            raw = ""
                        if not raw:
                            continue
                        md = raw
                    bbox = _pdfplumber_bbox_to_pdf(page, table.bbox)
                    caption = None
                    header = rows[0] if rows else None
                    if header:
                        caption = "Table: " + " | ".join((c or "").strip() for c in header if c)
                    image_key = None
                    if pdf is not None:
                        try:
                            fpage = pdf[page.page_number - 1]
                            clip = _pdf_to_fitz_rect(fpage, bbox)
                            pix = fpage.get_pixmap(clip=clip, dpi=72)
                            png = pix.tobytes("png")
                            image_key = storage_service.save_bytes(
                                document_id,
                                f"figures/table-{uuid.uuid4().hex[:12]}.png",
                                png,
                            )
                        except Exception as e:
                            logger.debug("Table screenshot failed: %s", e)
                    chunks.append(
                        _make_chunk(
                            chunk_type="table",
                            content=md,
                            page_number=page.page_number,
                            bbox=bbox,
                            caption=caption,
                            image_key=image_key,
                        )
                    )
                    # Repeat headers on each data row so BM25 can match a single fact.
                    if rows and len(rows) > 2:
                        header = rows[0]
                        for row in rows[1:]:
                            row_md = table_to_markdown([header, row])
                            if row_md.count("|") < 4:
                                continue
                            chunks.append(
                                _make_chunk(
                                    chunk_type="table",
                                    content=row_md,
                                    page_number=page.page_number,
                                    bbox=bbox,
                                    caption=caption,
                                    image_key=image_key,
                                )
                            )
    except Exception as e:
        logger.warning("Table extraction failed: %s", e)
    finally:
        if pdf is not None:
            pdf.close()
    return chunks


def extract_figures(file_bytes: bytes, document_id: str) -> List[dict]:
    if not getattr(settings, "ENABLE_STRUCTURED_CHUNKS", True):
        return []
    try:
        import fitz
    except Exception as e:
        logger.warning("PyMuPDF unavailable for figures: %s", e)
        return []

    min_px = getattr(settings, "MIN_FIGURE_PX", 40)
    chunks: List[dict] = []
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as e:
        logger.warning("PyMuPDF open failed for figures: %s", e)
        return []

    try:
        for page_index, page in enumerate(doc):
            images = page.get_images(full=True) or []
            seen_xrefs = set()
            for img in images:
                xref = img[0]
                if xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)
                try:
                    rects = page.get_image_rects(xref) or []
                except Exception:
                    rects = []
                if not rects:
                    continue
                rect = rects[0]
                if rect.width < min_px or rect.height < min_px:
                    continue
                try:
                    pix = fitz.Pixmap(doc, xref)
                    if pix.n > 4:
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                    png = pix.tobytes("png")
                except Exception as e:
                    logger.debug("Figure pixmap failed: %s", e)
                    continue
                caption = _caption_near_rect(page, rect)
                image_key = storage_service.save_bytes(
                    document_id,
                    f"figures/{uuid.uuid4().hex[:12]}.png",
                    png,
                )
                bbox = _fitz_rect_to_pdf(page, rect)
                label = caption or f"Figure on page {page_index + 1}"
                content = f"[Figure] {label}"
                chunks.append(
                    _make_chunk(
                        chunk_type="figure",
                        content=content,
                        page_number=page_index + 1,
                        bbox=bbox,
                        caption=caption or label,
                        image_key=image_key,
                    )
                )
    finally:
        doc.close()
    return chunks


def extract_structured(file_bytes: bytes, document_id: str) -> List[dict]:
    tables = extract_tables(file_bytes, document_id)
    figures = extract_figures(file_bytes, document_id)
    logger.info(
        "Structured extract: %s tables, %s figures (doc=%s)",
        len(tables),
        len(figures),
        document_id,
    )
    return tables + figures
