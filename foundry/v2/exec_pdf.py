"""Executive-summary PDF composer — an ISOLATED, defensive artifact generator.

Design rules (do-no-harm):
  * reportlab is imported LAZILY, inside the function, never at module load. If reportlab is absent in
    a deployment, importing THIS module still succeeds; only exec_summary_pdf() raises, and the caller
    turns that into a clean 503 — app boot and every existing route are untouched.
  * Pure-Python dependency (reportlab needs only pillow + charset-normalizer, no system libraries), so
    it installs cleanly on Railway without Pango/Cairo-style surprises.
  * Reads the SAME generated exec-summary content the on-screen summary and the Excel exhibit use
    (verdict lines, issue families, sign-off actions, the input/modeled finding streams), so the PDF
    can't drift from the other two surfaces.

The output is a clean light-on-white client document — not a screenshot of the dark UI.
"""
from __future__ import annotations

import io


def exec_summary_pdf(cfg: dict, res: dict) -> bytes:
    """Compose the executive summary as a PDF and return the bytes. Raises RuntimeError if the PDF
    toolkit is unavailable (caller should surface a 503), so a missing dependency never crashes boot."""
    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle)
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_LEFT
    except Exception as e:  # pragma: no cover - exercised only where reportlab is absent
        raise RuntimeError(f"PDF toolkit unavailable: {e}")

    from . import verdict as V

    # ---- palette (light document, not the dark UI) ----
    NAVY = colors.HexColor("#0A1830")
    GOLD = colors.HexColor("#B07E2E")
    MUTE = colors.HexColor("#56617A")
    RULE = colors.HexColor("#D6DCE6")
    BADRED = colors.HexColor("#B23B3B")

    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("H1", parent=ss["Title"], fontName="Helvetica-Bold",
                        fontSize=20, textColor=NAVY, spaceAfter=2, alignment=TA_LEFT)
    sub = ParagraphStyle("Sub", parent=ss["Normal"], fontName="Helvetica",
                         fontSize=9, textColor=MUTE, spaceAfter=10)
    h2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName="Helvetica-Bold",
                        fontSize=12.5, textColor=NAVY, spaceBefore=14, spaceAfter=5)
    body = ParagraphStyle("Body", parent=ss["Normal"], fontName="Helvetica",
                          fontSize=9.5, textColor=colors.HexColor("#1D2735"), leading=13, spaceAfter=4)
    small = ParagraphStyle("Small", parent=ss["Normal"], fontName="Helvetica",
                           fontSize=8.5, textColor=MUTE, leading=11)

    def esc(s):
        return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    bank = cfg.get("proposed_bank") or cfg.get("client_legal_name") or "De novo applicant"
    story = []

    # ---- header ----
    story.append(Paragraph("Executive Summary", h1))
    _meta = []
    if res.get("config_hash"):
        _meta.append(f"Run {esc(str(res['config_hash'])[:10])}")
    if res.get("engine_version"):
        _meta.append("Engine " + esc(str(res["engine_version"]).replace("foundry-engine ", "")))
    story.append(Paragraph(esc(bank) + ("  ·  " + "  ·  ".join(_meta) if _meta else ""), sub))

    # ---- the call: verdict lines ----
    story.append(Paragraph("The call", h2))
    for line in (V.verdict_lines(cfg, res) or []):
        story.append(Paragraph("•&nbsp;&nbsp;" + esc(line), body))

    # ---- decision drivers: issue families ----
    fams = V.issue_families(res) or []
    if fams:
        story.append(Paragraph("Decision drivers", h2))
        for fm in fams:
            nm = esc(fm.get("family", ""))
            concern = esc(fm.get("concern", ""))
            story.append(Paragraph(f"<b>{nm}</b> — {concern}", body))

    # ---- required before sign-off ----
    acts = V.sign_off_actions(res) or []
    if acts:
        story.append(Paragraph("Required before sign-off", h2))
        for i, a in enumerate(acts, 1):
            tag = " (affects verdict)" if a.get("affects_verdict") else ""
            story.append(Paragraph(f"{i}.&nbsp;{esc(a.get('text',''))}{esc(tag)}", body))

    # ---- stream 1: input reasonableness ----
    all_flags = res.get("flags") or []
    input_flags = [f for f in all_flags if f.get("source") != "modeled"]
    story.append(Paragraph("Are the assumptions credible?", h2))
    story.append(Paragraph("Input reasonableness — each raw assumption judged against real-peer bands.", small))
    if input_flags:
        rows = [["Finding", "Severity", "Observation"]]
        for f in input_flags:
            rows.append([esc(f.get("id", "")), esc(f.get("sev", "")),
                         Paragraph(esc(f.get("text", "")), small)])
        t = Table(rows, colWidths=[1.05 * inch, 0.7 * inch, 4.75 * inch], repeatRows=1)
        t.setStyle(_table_style(colors, NAVY, RULE))
        story.append(Spacer(1, 4)); story.append(t)
    else:
        story.append(Paragraph("No input assumption fell outside its reasonableness band.", body))

    # ---- stream 2: modeled challenges ----
    modeled = [f for f in all_flags if f.get("source") == "modeled"] + (res.get("modeled_challenges") or [])
    story.append(Paragraph("Does the modeled bank hold together?", h2))
    story.append(Paragraph("Modeled challenges — findings from the engine's own projected outputs.", small))
    if modeled:
        rows = [["Finding", "Severity", "Modeled observation"]]
        for m in sorted(modeled, key=lambda x: x.get("sev") != "severe"):
            rows.append([esc(m.get("id", "")), esc(m.get("sev", "")),
                         Paragraph(esc(m.get("text", "")), small)])
        t = Table(rows, colWidths=[1.4 * inch, 0.7 * inch, 4.4 * inch], repeatRows=1)
        t.setStyle(_table_style(colors, NAVY, RULE))
        story.append(Spacer(1, 4)); story.append(t)
    else:
        story.append(Paragraph("No modeled-output exceptions across the projection.", body))

    story.append(Spacer(1, 14))
    story.append(Paragraph(
        "Generated by Foundry. This planning exhibit accompanies, and does not replace, the full "
        "results workbook. Figures are modeled projections, not a filed business plan.", small))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER,
                            leftMargin=0.75 * inch, rightMargin=0.75 * inch,
                            topMargin=0.7 * inch, bottomMargin=0.7 * inch,
                            title=f"Executive Summary — {bank}")
    doc.build(story)
    return buf.getvalue()


def _table_style(colors, header_bg, rule):
    from reportlab.platypus import TableStyle
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), header_bg),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("FONTNAME", (0, 1), (1, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#1D2735")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, rule),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F6FA")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ])
