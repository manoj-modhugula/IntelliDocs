"""400+ atomic claims from the hard corpus: supported paraphrases + plausible errors."""

from __future__ import annotations

import json
from pathlib import Path

from build_hard_set import CITIES, DEPOTS, FLOW, PARTS, generate

OUT = Path(__file__).parent / "nli_heldout.json"


def main():
    generate()
    items = []
    # 25 plants × (8 supported + 2 unsupported) = 250, plus extras to 400+
    for i, city in enumerate(CITIES):
        depot = DEPOTS[i % len(DEPOTS)]
        days = 7 + (i * 3) % 21
        flow = FLOW[i % len(FLOW)]
        part = PARTS[i % 4][0]
        price = 18.0 + i
        evidence = (
            f"The {depot} in {city} retains audit trails for {days} days after each shift. "
            f"Spare parts grid lists the {part} at {price:.2f} USD. "
            f"The subsystem overview paints coolant flow {flow}."
        )
        supported = [
            f"The {depot} in {city} retains audit trails for {days} days.",
            f"Shift logs at the {city} {depot} are kept for {days} days.",
            f"The {part} is listed at {price:.2f} USD on the spare parts grid.",
            f"Coolant flow on the {city} subsystem overview is {flow}.",
            f"Operators at the {city} {depot} must archive the shift log before the window closes.",
            f"The {city} plant documents a {days}-day audit-trail window.",
            f"The spare-parts price for the {part} is {price:.2f}.",
            f"The {city} schematic indicates coolant moving {flow}.",
            f"{city}'s {depot} keeps audit trails for {days} days after each shift.",
            f"The {city} spare-parts grid prices the {part} at {price:.2f} USD.",
            f"Audit trails at the {depot} in {city} expire after {days} days.",
            f"The painted coolant direction at {city} is {flow}.",
            f"The {city} {depot} archives the shift log within a {days}-day window.",
            f"List price {price:.2f} applies to the {part} at {city}.",
        ]
        for c in supported:
            items.append({"claim": c, "evidence": evidence, "label": "entailment", "plant": city})
        # Two plausible errors per plant → 50/400 = 0.125 prior if 25 plants (350+50).
        unsupported = [
            f"The {depot} in {city} retains audit trails for {days + 11} days.",
            f"The {city} plant offers same-day on-site nuclear certification.",
        ]
        for c in unsupported:
            items.append({"claim": c, "evidence": evidence, "label": "neutral", "plant": city})
    OUT.write_text(json.dumps({"items": items}, indent=2))
    n = len(items)
    uns = sum(1 for x in items if x["label"] != "entailment")
    print(f"wrote {n} claims unsupported_prior={uns/n:.3f} -> {OUT}")


if __name__ == "__main__":
    main()
