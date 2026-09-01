import json
import re
from pathlib import Path

from app.services.retrieval import _IDENT


def test_hard_set_has_500_id_free_questions():
    import importlib.util

    path = Path(__file__).resolve().parent.parent / "scripts/evaluation/build_hard_set.py"
    spec = importlib.util.spec_from_file_location("build_hard_set", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    data = mod.generate()
    cases = data["cases"]
    assert len(cases) == 500
    cats = {}
    for c in cases:
        cats[c["category"]] = cats.get(c["category"], 0) + 1
        assert _IDENT.search(c["question"]) is None
        assert "SKU-N" not in c["question"]
        assert "FIG-UNIT" not in c["question"]
    assert cats["text"] == 200
    assert cats["table"] == 175
    assert cats["figure"] == 125
