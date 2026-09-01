import json
from pathlib import Path

from app.services.grounding import filter_answer, nli_label, split_claims

GROUND = Path(__file__).resolve().parent.parent / "scripts/evaluation/nli_ground_truth.json"


class _Chunk:
    def __init__(self, content):
        self.content = content
        self.caption = None


def test_held_out_entailment_items_keep():
    items = json.loads(GROUND.read_text())["items"]
    entailed = [i for i in items if i["label"] == "entailment"]
    assert len(entailed) >= 10
    hits = sum(1 for i in entailed if nli_label(i["claim"], i["evidence"]) == "entailment")
    assert hits / len(entailed) >= 0.7


def test_held_out_unsupported_items_not_entailed():
    items = json.loads(GROUND.read_text())["items"]
    bad = [i for i in items if i["label"] != "entailment"]
    misses = sum(1 for i in bad if nli_label(i["claim"], i["evidence"]) != "entailment")
    assert misses / len(bad) >= 0.7


def test_planted_hallucination_stripped():
    evidence = "Customers may request a refund within 14 days of purchase."
    answer = "Refunds are allowed within 14 days. The CEO lives on Mars."
    filtered, dropped, _ = filter_answer(answer, [(_Chunk(evidence), 1.0)])
    assert "Mars" not in filtered
    assert any("Mars" in d for d in dropped)
    assert "14" in filtered
