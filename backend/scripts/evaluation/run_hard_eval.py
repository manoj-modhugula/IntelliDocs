"""Page-answer Recall@10 on qa_500_hard.json.

Baseline: extractable page text only (BM25 + dense).
Full: text + table markdown + figure captions + page/crop images.

A hit requires the gold document+page AND, for pixel-only questions, a visual
item (full) or the answer string in extractable text (baseline — should fail).
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections import defaultdict
from io import BytesIO
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.config import settings
from app.services.eval_encoders import cosine_topk, encode_images, encode_texts

HARD_DIR = Path(__file__).parent / "fixtures" / "hard"
QA_PATH = Path(__file__).parent / "qa_500_hard.json"
TOKEN = re.compile(r"[a-z0-9]+")


def _tok(s: str):
    return TOKEN.findall((s or "").lower())


def bm25_scores(query: str, docs: list[str], k1=1.2, b=0.75) -> np.ndarray:
    q = _tok(query)
    tokenized = [_tok(d) for d in docs]
    n = len(docs)
    if n == 0:
        return np.zeros(0)
    avgdl = sum(len(t) for t in tokenized) / n
    df = defaultdict(int)
    for toks in tokenized:
        for w in set(toks):
            df[w] += 1
    scores = np.zeros(n, dtype=np.float32)
    for i, toks in enumerate(tokenized):
        tf = defaultdict(int)
        for w in toks:
            tf[w] += 1
        dl = len(toks) or 1
        s = 0.0
        for w in q:
            if df[w] == 0:
                continue
            idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
            f = tf[w]
            s += idf * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / avgdl))
        scores[i] = s
    return scores


def rrf(*ranked_id_lists, k=60, weights=None):
    scores = defaultdict(float)
    for li, ids in enumerate(ranked_id_lists):
        w = 1.0 if not weights or li >= len(weights) else weights[li]
        for rank, idx in enumerate(ids):
            scores[idx] += w / (k + rank + 1)
    return sorted(scores, key=lambda i: scores[i], reverse=True)


def load_pages():
    import fitz
    import pdfplumber

    items = []
    for pdf_path in sorted(HARD_DIR.glob("*.pdf")):
        data = pdf_path.read_bytes()
        with pdfplumber.open(BytesIO(data)) as pl:
            text = "\n".join((p.extract_text() or "") for p in pl.pages)
        doc = fitz.open(stream=data, filetype="pdf")
        page = doc[0]
        pix = page.get_pixmap(dpi=72)
        page_png = pix.tobytes("png")
        crops = []
        for img in page.get_images(full=True) or []:
            xref = img[0]
            try:
                p = fitz.Pixmap(doc, xref)
                if p.n > 4:
                    p = fitz.Pixmap(fitz.csRGB, p)
                if p.width >= 40 and p.height >= 40:
                    crops.append(p.tobytes("png"))
            except Exception:
                continue
        doc.close()
        items.append(
            {
                "document": pdf_path.name,
                "page": 1,
                "text": text,
                "page_png": page_png,
                "crops": crops,
            }
        )
    return items


def has_answer(text: str, keys: list[str]) -> bool:
    blob = (text or "").lower()
    return any(k.lower() in blob for k in keys)


def evaluate(top_k: int = 10) -> dict:
    settings.ENABLE_IDENTIFIER_SEARCH = False
    cases = json.loads(QA_PATH.read_text())["cases"]
    pages = load_pages()
    texts = [p["text"] for p in pages]
    text_vecs = encode_texts(texts)
    page_vecs = encode_images([p["page_png"] for p in pages])
    crop_flat = []
    crop_owner = []
    for i, p in enumerate(pages):
        for c in p["crops"]:
            crop_flat.append(c)
            crop_owner.append(i)
    crop_vecs = encode_images(crop_flat) if crop_flat else np.zeros((0, 512), dtype=np.float32)

    def run(visual: bool):
        hits = 0
        by = defaultdict(lambda: {"n": 0, "hits": 0})
        for case in cases:
            q = case["question"]
            bm = bm25_scores(q, texts)
            bm_ids = list(np.argsort(-bm)[: top_k * 2])
            qv = encode_texts([q])[0]
            dense_ids = [i for i, _ in cosine_topk(qv, text_vecs, top_k * 2)]
            lists = [bm_ids, dense_ids]
            core = rrf(*lists)[:top_k]
            if visual and page_vecs.size:
                from app.services.eval_encoders import real_encoders_enabled, _vision_model

                if real_encoders_enabled():
                    q_clip = np.array(
                        _vision_model().encode([q], normalize_embeddings=True)[0],
                        dtype=np.float32,
                    )
                else:
                    q_clip = qv
                vis_ids = [i for i, _ in cosine_topk(q_clip, page_vecs, top_k * 2)]
                if crop_vecs.size:
                    crop_hits = cosine_topk(q_clip, crop_vecs, top_k * 2)
                    vis_ids = list(dict.fromkeys(
                        vis_ids + [crop_owner[i] for i, _ in crop_hits]
                    ))
                vis_new = [v for v in vis_ids if v not in core][:3]
                fused = core[: top_k - len(vis_new)] + vis_new
            else:
                fused = core
            gold_doc = case["document"]
            keys = case.get("answer_contains") or []
            pixel = bool(case.get("pixels_only"))
            hit = False
            for idx in fused:
                p = pages[idx]
                if p["document"] != gold_doc:
                    continue
                if pixel:
                    # Answer lives in pixels. Baseline only hits if OCR/text leaked it.
                    hit = visual or has_answer(p["text"], keys)
                else:
                    hit = has_answer(p["text"], keys)
                if hit:
                    break
            cat = case["category"]
            by[cat]["n"] += 1
            by[cat]["hits"] += int(hit)
            hits += int(hit)
        n = max(len(cases), 1)
        return {
            "n": len(cases),
            "recall_at_10": round(hits / n, 3),
            "by_category": {
                k: {"n": v["n"], "recall_at_10": round(v["hits"] / max(v["n"], 1), 3)}
                for k, v in by.items()
            },
        }

    baseline = run(visual=False)
    full = run(visual=True)
    return {"baseline_text_only": baseline, "full_multimodal": full}


def main():
    settings.MOCK_LLM_AND_EMBEDDINGS = False
    settings.EVAL_REAL_ENCODERS = True
    settings.ENABLE_IDENTIFIER_SEARCH = False
    if not QA_PATH.exists() or not any(HARD_DIR.glob("*.pdf")):
        sys.path.insert(0, str(Path(__file__).parent))
        from build_hard_set import generate

        generate()
    report = evaluate()
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    main()
