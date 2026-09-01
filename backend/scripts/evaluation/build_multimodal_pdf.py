"""Build a small PDF with a text policy, a ruled table, and a captioned figure."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Optional


def build_multimodal_pdf(
    *,
    policy_line: str = "Customers may request a refund within 14 days of purchase.",
    sku: str = "SKU-ACME-1",
    price: str = "19.99",
    fig_id: str = "FIG-PUMP-07",
    fig_label: str = "centrifugal pump diagram",
) -> bytes:
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 72), "ACME Equipment Manual", fontsize=16)
    page.insert_text((72, 100), policy_line, fontsize=11)

    # Ruled 2x3 table (text placed as show-text, not textbox, so extractors see glyphs)
    x0, y0 = 72, 140
    col_w, row_h = 180, 24
    headers = ["SKU", "Price"]
    rows = [headers, [sku, price], ["SKU-ACME-2", "4.50"]]
    for r, row in enumerate(rows):
        for c, cell in enumerate(row):
            rect = fitz.Rect(x0 + c * col_w, y0 + r * row_h, x0 + (c + 1) * col_w, y0 + (r + 1) * row_h)
            page.draw_rect(rect, color=(0, 0, 0), width=0.8)
            page.insert_text((rect.x0 + 8, rect.y0 + 16), cell, fontsize=11)

    # Caption + figure image
    cap_y = 240
    page.insert_text((72, cap_y), f"Figure: {fig_id} {fig_label}", fontsize=11)

    img = fitz.open()
    ip = img.new_page(width=240, height=120)
    ip.draw_rect(ip.rect, color=(0.1, 0.2, 0.5), fill=(0.15, 0.35, 0.7))
    ip.insert_textbox(ip.rect + (8, 20, -8, -8), f"{fig_id}\n{fig_label}", fontsize=14, color=(1, 1, 1))
    pix = ip.get_pixmap()
    img.close()
    img_rect = fitz.Rect(72, cap_y + 10, 72 + 240, cap_y + 10 + 120)
    page.insert_image(img_rect, pixmap=pix)

    buf = BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def write_fixture(path: Optional[Path] = None) -> Path:
    dest = path or Path(__file__).resolve().parent / "fixtures" / "multimodal_manual.pdf"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(build_multimodal_pdf())
    return dest


if __name__ == "__main__":
    out = write_fixture()
    print(out)
