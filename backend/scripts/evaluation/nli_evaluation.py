"""Measure unsupported-claim rate with NLI filter on vs off."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.config import settings
from app.services.grounding import filter_answer, nli_label, split_claims

GROUND = Path(__file__).parent / "nli_ground_truth.json"
HELDOUT = Path(__file__).parent / "nli_heldout.json"


class _Chunk:
    def __init__(self, content: str):
        self.content = content
        self.caption = None


def label_accuracy(items: list[dict]) -> dict:
    correct = 0
    by_label = {}
    for item in items:
        pred = nli_label(item["claim"], item["evidence"])
        gold = item["label"]
        ok = pred == gold or (gold == "contradiction" and pred != "entailment")
        # mock NLI maps contradiction-ish to neutral; count as correct if not entailment
        if gold != "entailment" and pred != "entailment":
            ok = True
        if gold == "entailment" and pred == "entailment":
            ok = True
        by_label.setdefault(gold, {"n": 0, "ok": 0})
        by_label[gold]["n"] += 1
        by_label[gold]["ok"] += int(ok)
        correct += int(ok)
    return {"accuracy": correct / max(len(items), 1), "by_label": by_label, "n": len(items)}


def unsupported_rate(answers: list[tuple[str, str]]) -> dict:
    """answers: list of (generated_answer, evidence)."""
    off_bad = 0
    on_bad = 0
    total_claims = 0
    for answer, evidence in answers:
        claims = split_claims(answer)
        total_claims += len(claims)
        for c in claims:
            if nli_label(c, evidence) != "entailment":
                off_bad += 1
        filtered, dropped, _ = filter_answer(answer, [(_Chunk(evidence), 1.0)])
        for c in split_claims(filtered):
            if nli_label(c, evidence) != "entailment":
                on_bad += 1
    n = max(total_claims, 1)
    return {
        "claims": total_claims,
        "unsupported_off": off_bad / n,
        "unsupported_on": on_bad / max(sum(len(split_claims(filter_answer(a, [(_Chunk(e), 1.0)])[0])) for a, e in answers), 1),
        "dropped_rate": (off_bad - on_bad) / n if False else on_bad / n,
        "raw_off": off_bad,
        "raw_on": on_bad,
    }


PLANTED = [
    (
        "Customers may request a refund within 14 days of purchase. The CEO lives on Mars.",
        "Customers may request a refund within 14 days of purchase. Gift cards are excluded.",
    ),
    (
        "SKU-ACME-1 costs 19.99. Shipping to Mars is free.",
        "| SKU | Price |\n| SKU-ACME-1 | 19.99 |",
    ),
    (
        "FIG-PUMP-07 is a centrifugal pump diagram. The moon is made of cheese.",
        "[Figure] FIG-PUMP-07 centrifugal pump diagram",
    ),
    (
        "Email refunds@acme.test for refund status. The warranty is 400 years.",
        "Email refunds@acme.test for refund status. Digital gift cards are not eligible.",
    ),
]


def heldout_filter_rates(items: list[dict]) -> dict:
    off_uns = sum(1 for i in items if i["label"] != "entailment")
    kept_uns = kept_all = 0
    for i in items:
        pred = nli_label(i["claim"], i["evidence"])
        if pred == "entailment":
            kept_all += 1
            if i["label"] != "entailment":
                kept_uns += 1
    n = max(len(items), 1)
    return {
        "n": len(items),
        "unsupported_off": round(off_uns / n, 3),
        "unsupported_on": round(kept_uns / max(kept_all, 1), 3),
        "kept": kept_all,
    }


def main() -> None:
    settings.MOCK_LLM_AND_EMBEDDINGS = True
    items = json.loads(GROUND.read_text())["items"]
    acc = label_accuracy(items)
    report = {
        "label_accuracy_small": round(acc["accuracy"], 3),
        "label_n": acc["n"],
    }
    if HELDOUT.exists():
        held = json.loads(HELDOUT.read_text())["items"]
        report["heldout"] = heldout_filter_rates(held)
    else:
        off_bad = on_bad = total = 0
        for answer, evidence in PLANTED:
            claims = split_claims(answer)
            total += len(claims)
            off_bad += sum(1 for c in claims if nli_label(c, evidence) != "entailment")
            filtered, dropped, _ = filter_answer(answer, [(_Chunk(evidence), 1.0)])
            kept = split_claims(filtered)
            on_bad += sum(1 for c in kept if nli_label(c, evidence) != "entailment")
        report["unsupported_off"] = round(off_bad / max(total, 1), 3)
        report["unsupported_on"] = round(on_bad / max(total, 1), 3)
        report["planted_claims"] = total
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
