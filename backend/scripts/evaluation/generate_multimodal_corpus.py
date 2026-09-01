"""Generate labeled multimodal PDFs + 500 retrieval queries.

Ground truth is produced by the generator (doc + fact id), not by the retriever.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import importlib.util

_builder = Path(__file__).with_name("build_multimodal_pdf.py")
_spec = importlib.util.spec_from_file_location("build_multimodal_pdf", _builder)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader
_spec.loader.exec_module(_mod)
build_multimodal_pdf = _mod.build_multimodal_pdf

OUT = Path(__file__).parent / "fixtures" / "multimodal"
QA_PATH = Path(__file__).parent / "qa_500.json"


def generate(n_docs: int = 25) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    cases = []
    for i in range(n_docs):
        days = 7 + (i % 21)
        sku = f"SKU-N{i:03d}"
        price = f"{10 + (i % 90)}.99"
        fig_id = f"FIG-UNIT-{i:03d}"
        fig_label = f"assembly diagram unit {i}"
        policy = f"Site {i} retains logs for {days} days. Contact ops{i}@acme.test for access."
        pdf = build_multimodal_pdf(
            policy_line=policy,
            sku=sku,
            price=price,
            fig_id=fig_id,
            fig_label=fig_label,
        )
        name = f"site_{i:03d}.pdf"
        (OUT / name).write_bytes(pdf)

        # 14 text + 3 table + 3 figure = 20 per doc → 500 at 25 docs
        text_qs = [
            f"How long does site {i} retain logs?",
            f"What is the log retention period at site {i}?",
            f"Site {i} keeps logs for how many days?",
            f"Which retention window applies to site {i}?",
            f"How many days of logs does site {i} store?",
            f"What retention policy does site {i} use?",
            f"For site {i}, how long are logs kept?",
            f"Identify the log retention days for site {i}.",
            f"Site {i} log retention duration?",
            f"How long are records retained at site {i}?",
            f"Give the retention days used by site {i}.",
            f"What is site {i}'s log keep period?",
            f"Retention length for logs at site {i}?",
            f"How long does site {i} keep operational logs?",
        ]
        for q in text_qs:
            cases.append(
                {
                    "question": q,
                    "relevant_keywords": [f"{days} days", f"Site {i}"],
                    "category": "text",
                    "document": name,
                    "fact_id": f"site-{i}-retention",
                }
            )
        table_qs = [
            f"What is the price of {sku}?",
            f"How much does {sku} cost?",
            f"Look up {sku} in the price table.",
        ]
        for q in table_qs:
            cases.append(
                {
                    "question": q,
                    "relevant_keywords": [sku, price],
                    "category": "table",
                    "document": name,
                    "fact_id": f"sku-{i}",
                }
            )
        fig_qs = [
            f"What does figure {fig_id} show?",
            f"Describe the diagram labeled {fig_id}.",
            f"Which assembly is in figure {fig_id}?",
        ]
        for q in fig_qs:
            cases.append(
                {
                    "question": q,
                    "relevant_keywords": [fig_id, "assembly"],
                    "category": "figure",
                    "document": name,
                    "fact_id": f"fig-{i}",
                }
            )
    payload = {"workspace_id": "eval-multimodal", "cases": cases}
    QA_PATH.write_text(json.dumps(payload, indent=2))
    return payload


if __name__ == "__main__":
    data = generate()
    print(f"docs={len(list(OUT.glob('*.pdf')))} cases={len(data['cases'])} -> {QA_PATH}")
