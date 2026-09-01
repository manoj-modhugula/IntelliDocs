"""Build an ID-free 500-query multimodal set.

Mixture (a priori, not tuned after seeing scores):
  200 text paraphrases (answer in extractable body text)
   75 digital-table lookups (cells also appear in flattened page text)
  100 image-table lookups (prices exist only as pixels)
  125 figure lookups (answer exists only as pixels)

Questions never contain SKU-/FIG-/site-N identifiers.
"""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

OUT_DIR = Path(__file__).parent / "fixtures" / "hard"
QA_PATH = Path(__file__).parent / "qa_500_hard.json"

CITIES = [
    "Halifax", "Tulsa", "Boise", "Tacoma", "Durham", "Omaha", "Irvine",
    "Akron", "Tempe", "Provo", "Eugene", "Mobile", "Reno", "Spokane",
    "Laredo", "Irving", "Hialeah", "Garland", "Scottsdale", "Gilbert",
    "Glendale", "Chandler", "Norfolk", "Orlando", "Pittsburgh",
]
DEPOTS = [
    "northern depot", "harbor workshop", "ridge plant", "canyon yard",
    "lakeside shop",
]
FLOW = ["east to west", "west to east", "north to south", "south to north"]
PARTS = [
    ("bronze seawater impeller", "impeller"),
    ("nitrile hatch gasket", "gasket"),
    ("ceramic spindle bearing", "bearing"),
    ("graphite packing ring", "packing"),
]


def _text_page(doc, city: str, depot: str, days: int):
    import fitz

    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 64), f"ACME plant manual — {city}", fontsize=16)
    body = (
        f"The {depot} in {city} retains audit trails for {days} days after each shift. "
        f"Operators must archive the shift log before the window closes. "
        f"Digital gift cards issued at this plant follow the corporate refund desk."
    )
    page.insert_textbox(fitz.Rect(72, 96, 540, 180), body, fontsize=11)
    # Digital table (extractable)
    x0, y0, col_w, row_h = 72, 200, 200, 22
    rating = f"{12 + (days % 9)} knots"
    rows = [
        ["Component", "Rating", "Hours"],
        ["seawater pump", rating, str(800 + days)],
        ["backup impeller housing", f"{city} spec", "n/a"],
    ]
    for r, row in enumerate(rows):
        for c, cell in enumerate(row):
            rect = fitz.Rect(x0 + c * col_w, y0 + r * row_h, x0 + (c + 1) * col_w, y0 + (r + 1) * row_h)
            page.draw_rect(rect, color=(0, 0, 0), width=0.7)
            page.insert_text((rect.x0 + 6, rect.y0 + 15), cell, fontsize=10)
    page.insert_text((72, 280), "Spare parts (see grid image)", fontsize=11)
    return page, rating


def _image_table_png(city: str, prices: dict) -> bytes:
    import fitz

    img = fitz.open()
    ip = img.new_page(width=420, height=160)
    ip.draw_rect(ip.rect, color=(0.1, 0.1, 0.1), fill=(0.95, 0.95, 0.92))
    ip.insert_text((12, 18), f"Spare parts grid — {city}", fontsize=11)
    y = 40
    ip.insert_text((12, y), "Item", fontsize=10)
    ip.insert_text((280, y), "USD", fontsize=10)
    for name, price in prices.items():
        y += 22
        ip.insert_text((12, y), name, fontsize=10)
        ip.insert_text((280, y), f"{price:.2f}", fontsize=10)
    pix = ip.get_pixmap()
    data = pix.tobytes("png")
    img.close()
    return data


def _figure_png(flow: str) -> bytes:
    import fitz

    img = fitz.open()
    ip = img.new_page(width=280, height=140)
    ip.draw_rect(ip.rect, color=(0.1, 0.2, 0.5), fill=(0.12, 0.32, 0.62))
    ip.insert_textbox(
        ip.rect + (10, 24, -10, -10),
        f"COOLANT FLOW {flow.upper()}",
        fontsize=14,
        color=(1, 1, 1),
    )
    pix = ip.get_pixmap()
    data = pix.tobytes("png")
    img.close()
    return data


def build_pdf(i: int) -> tuple[bytes, dict]:
    import fitz

    city = CITIES[i]
    depot = DEPOTS[i % len(DEPOTS)]
    days = 7 + (i * 3) % 21
    flow = FLOW[i % len(FLOW)]
    prices = {
        PARTS[0][0]: 18.0 + i,
        PARTS[1][0]: 4.5 + (i % 5) * 0.25,
        PARTS[2][0]: 31.0 + (i % 7),
        PARTS[3][0]: 2.0 + (i % 4) * 0.5,
    }
    doc = fitz.open()
    page, rating = _text_page(doc, city, depot, days)
    # image table
    tbl = _image_table_png(city, prices)
    rect = fitz.Rect(72, 300, 72 + 420, 300 + 160)
    page.insert_image(rect, stream=tbl)
    # figure (answer only in pixels)
    page.insert_text((72, 480), "Figure: subsystem overview", fontsize=11)
    fig = _figure_png(flow)
    frect = fitz.Rect(72, 492, 72 + 280, 492 + 140)
    page.insert_image(frect, stream=fig)
    buf = BytesIO()
    doc.save(buf)
    doc.close()
    meta = {
        "city": city,
        "depot": depot,
        "days": days,
        "flow": flow,
        "prices": prices,
        "rating": rating,
        "page": 1,
        "doc": f"plant_{i:02d}_{city.lower()}.pdf",
    }
    return buf.getvalue(), meta


def generate(n_docs: int = 25) -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cases = []
    for i in range(n_docs):
        pdf, meta = build_pdf(i)
        path = OUT_DIR / meta["doc"]
        path.write_bytes(pdf)
        city, depot, days = meta["city"], meta["depot"], meta["days"]
        # 8 text paraphrases
        text_qs = [
            f"How long does the {depot} in {city} keep audit trails?",
            f"What is the audit-trail retention at the {depot} in {city}?",
            f"After a shift, how many days does {city}'s {depot} retain logs?",
            f"Retention window for shift logs at the {city} {depot}?",
            f"How long are audit trails stored by the {depot} located in {city}?",
            f"Give the log-keeping period used at the {city} {depot}.",
            f"The {depot} in {city} archives shift logs for how long?",
            f"What retention applies to audit trails at {city}'s {depot}?",
        ]
        for q in text_qs:
            cases.append(
                {
                    "question": q,
                    "category": "text",
                    "document": meta["doc"],
                    "page": 1,
                    "answer_contains": [f"{days} days", city],
                }
            )
        # 3 digital-table (rating is extractable)
        rating = meta["rating"]
        for q in [
            f"What speed rating is listed for the seawater pump at the {city} plant?",
            f"Which knot rating does the {city} seawater pump table use?",
            f"Hours aside, what is the seawater pump rating in the {city} component table?",
        ]:
            cases.append(
                {
                    "question": q,
                    "category": "table",
                    "document": meta["doc"],
                    "page": 1,
                    "answer_contains": [rating, "seawater pump"],
                }
            )
        # 4 image-table (prices only in pixels)
        part_name, _ = PARTS[i % 4]
        price = meta["prices"][part_name]
        for q in [
            f"What is the spare-parts grid price of the {part_name}?",
            f"How much does the {part_name} cost in the parts grid?",
            f"List price of the {part_name} on the spare parts grid?",
            f"USD amount shown for the {part_name} in the parts grid?",
        ]:
            cases.append(
                {
                    "question": q,
                    "category": "table",
                    "document": meta["doc"],
                    "page": 1,
                    "answer_contains": [f"{price:.2f}", part_name.split()[0]],
                    "pixels_only": True,
                }
            )
        # 5 figure (flow only in pixels; city disambiguates the plant, not the answer)
        flow = meta["flow"]
        for q in [
            f"Which way does coolant flow in the {city} subsystem overview?",
            f"Coolant flow direction on the {city} subsystem schematic?",
            f"In the {city} subsystem overview, coolant moves how?",
            f"What flow direction is painted on the {city} subsystem figure?",
            f"Does the {city} subsystem overview show eastward or westward coolant flow?",
        ]:
            cases.append(
                {
                    "question": q,
                    "category": "figure",
                    "document": meta["doc"],
                    "page": 1,
                    "answer_contains": [flow],
                    "pixels_only": True,
                }
            )
    payload = {
        "workspace_id": "eval-hard",
        "mixture": {"text": 200, "table": 175, "figure": 125},
        "cases": cases,
    }
    QA_PATH.write_text(json.dumps(payload, indent=2))
    return payload


if __name__ == "__main__":
    data = generate()
    print(f"docs={len(list(OUT_DIR.glob('*.pdf')))} cases={len(data['cases'])} -> {QA_PATH}")
