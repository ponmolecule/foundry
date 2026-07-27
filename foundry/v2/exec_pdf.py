"""Executive-summary PDF composer — captures EVERY section of the on-screen Executive Summary tab.

Design rules (do-no-harm):
  * reportlab is imported LAZILY, inside the function, never at module load. If reportlab is absent in
    a deployment, importing THIS module still succeeds; only exec_summary_pdf() raises, and the caller
    turns that into a clean 503 — app boot and every existing route are untouched.
  * Pure-Python dependency (reportlab needs only pillow + charset-normalizer, no system libraries).
  * Reads the SAME run_v2 result and verdict generators the on-screen summary uses, section for section.

Sections captured, in the tab's order: header · the call (verdict lines) · top issue families ·
required before sign-off · are the assumptions credible? (every input flag) · does the modeled bank
hold together? (every modeled flag + modeled challenge) · peer context · the evidence behind it
(scenario & constraint outcomes).
"""
from __future__ import annotations

import io


def exec_summary_pdf(cfg: dict, res: dict) -> bytes:
    """Compose the full executive summary as a PDF. Raises RuntimeError if the PDF toolkit is
    unavailable (caller should surface a 503), so a missing dependency never crashes boot."""
    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_LEFT
    except Exception as e:  # pragma: no cover
        raise RuntimeError(f"PDF toolkit unavailable: {e}")

    from . import verdict as V

    NAVY = colors.HexColor("#0A1830")
    MUTE = colors.HexColor("#56617A")
    RULE = colors.HexColor("#D6DCE6")
    INK = colors.HexColor("#1D2735")

    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("H1", parent=ss["Title"], fontName="Helvetica-Bold", fontSize=20,
                        textColor=NAVY, spaceAfter=2, alignment=TA_LEFT)
    sub = ParagraphStyle("Sub", parent=ss["Normal"], fontName="Helvetica", fontSize=8.5,
                         textColor=MUTE, spaceAfter=11)
    h2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=12.5,
                        textColor=NAVY, spaceBefore=13, spaceAfter=4)
    h3 = ParagraphStyle("H3", parent=ss["Normal"], fontName="Helvetica-Bold", fontSize=10.5,
                        textColor=NAVY, spaceAfter=3)
    introS = ParagraphStyle("Intro", parent=ss["Normal"], fontName="Helvetica-Oblique", fontSize=8.5,
                            textColor=MUTE, leading=11, spaceAfter=5)
    body = ParagraphStyle("Body", parent=ss["Normal"], fontName="Helvetica", fontSize=9.5,
                          textColor=INK, leading=13, spaceAfter=4)
    bullet = ParagraphStyle("Bullet", parent=body, leftIndent=10, spaceAfter=3)
    small = ParagraphStyle("Small", parent=ss["Normal"], fontName="Helvetica", fontSize=8.5,
                           textColor=MUTE, leading=11)
    cell = ParagraphStyle("Cell", parent=ss["Normal"], fontName="Helvetica", fontSize=8.5,
                          textColor=INK, leading=11)

    def esc(s):
        return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def clean_src(s):
        import re
        return re.sub(r"\s*\(edit with citation\)\s*", "", str(s or "")).strip()

    def sev_cell(sev):
        s = str(sev or "")
        col = "#B23B3B" if s == "severe" else "#56617A"
        return Paragraph(f'<font color="{col}">{esc(s)}</font>', cell)

    def tbl_style():
        from reportlab.platypus import TableStyle
        return TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.4, RULE),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F6FA")]),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ])

    def hdr(*labels):
        return [Paragraph(f"<b>{l}</b>", cell) for l in labels]

    bank = cfg.get("proposed_bank") or cfg.get("client_legal_name") or "De novo applicant"
    story = []

    # header
    story.append(Paragraph("Executive Summary", h1))
    import datetime as _dt
    meta = [esc(bank)]
    if res.get("config_hash"):
        meta.append("Run " + esc(str(res["config_hash"])[:10]))
    if res.get("engine_version"):
        meta.append("Engine " + esc(str(res["engine_version"]).replace("foundry-engine ", "")))
    meta.append("Generated " + _dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M") + "Z")
    story.append(Paragraph("  \u00b7  ".join(meta), sub))

    # the call
    story.append(Paragraph("The call", h2))
    for line in (V.verdict_lines(cfg, res) or ["No verdict generated."]):
        story.append(Paragraph("\u2022&nbsp;&nbsp;" + esc(line), bullet))

    # top issue families
    fams = V.issue_families(res) or []
    if fams:
        story.append(Paragraph("Top issue families \u2014 what to focus on", h2))
        for fm in fams:
            story.append(Paragraph(f"<b>{esc(fm.get('family',''))}</b> \u2014 {esc(fm.get('concern',''))}", body))

    # required before sign-off
    acts = V.sign_off_actions(res) or []
    if acts:
        story.append(Paragraph("Required before sign-off", h2))
        for i, a in enumerate(acts, 1):
            tag = "  (affects verdict)" if a.get("affects_verdict") else ""
            story.append(Paragraph(f"{i}.&nbsp;{esc(a.get('text',''))}{esc(tag)}", body))

    # stream 1 — input reasonableness (every input flag)
    all_flags = res.get("flags") or []
    input_flags = [f for f in all_flags if f.get("source") != "modeled"]
    story.append(Paragraph("Are the assumptions credible?", h2))
    story.append(Paragraph("Input reasonableness \u2014 each raw assumption judged against real-peer bands.", introS))
    if input_flags:
        rows = [hdr("Finding", "Severity", "Observation")]
        for f in input_flags:
            rows.append([Paragraph(esc(f.get("id", "")), cell), sev_cell(f.get("sev", "")),
                         Paragraph(esc(f.get("text", "")), cell)])
        t = Table(rows, colWidths=[1.15 * inch, 0.65 * inch, 4.7 * inch], repeatRows=1)
        t.setStyle(tbl_style()); story.append(t)
    else:
        story.append(Paragraph("No input assumption fell outside its reasonableness band.", body))

    # stream 2 — modeled challenges (every modeled flag + challenge)
    modeled = [f for f in all_flags if f.get("source") == "modeled"] + (res.get("modeled_challenges") or [])
    story.append(Paragraph("Does the modeled bank hold together?", h2))
    story.append(Paragraph("Modeled challenges \u2014 findings from the engine's own projected outputs.", introS))
    if modeled:
        rows = [hdr("Finding", "Severity", "Modeled observation")]
        for m in sorted(modeled, key=lambda x: x.get("sev") != "severe"):
            obs = esc(m.get("text", ""))
            if m.get("basis"):
                obs += f'<br/><font color="#6E7C93" size="7">Modeled basis: {esc(m["basis"])}</font>'
            rows.append([Paragraph(esc(m.get("id", "")), cell), sev_cell(m.get("sev", "")),
                         Paragraph(obs, cell)])
        t = Table(rows, colWidths=[1.35 * inch, 0.65 * inch, 4.5 * inch], repeatRows=1)
        t.setStyle(tbl_style()); story.append(t)
    else:
        story.append(Paragraph("No modeled-output exceptions across the projection.", body))

    # peer context
    peer = res.get("peer") or {}
    pcohort = peer.get("cohort") if isinstance(peer, dict) else None
    story.append(Paragraph("Peer context", h2))
    if pcohort:
        story.append(Paragraph(
            f"Benchmarked against <b>{esc(pcohort.get('n','\u2014'))} real de novo filers</b>. "
            f"Current-quarter stock measures (leverage, capital ratios) are like-for-like; selected "
            f"earnings measures are directional.", body))
    else:
        note = peer.get("note") if isinstance(peer, dict) else None
        story.append(Paragraph(esc(note or "Peer calibration attaches when resolved from the CharterIQ Call Report substrate."), small))

    # the evidence behind it — scenario & constraint outcomes
    ctests = res.get("constraint_tests") or []
    if ctests:
        story.append(Paragraph("The evidence behind it", h2))
        story.append(Paragraph("Scenario &amp; constraint outcomes", h3))
        scen = res.get("scenarios") or {}
        rows = [hdr("Scenario", "Constraint", "Value", "Limit", "Result", "Source")]
        for t0 in ctests:
            lbl = (scen.get(t0.get("scenario"), {}) or {}).get("label") or t0.get("scenario", "")
            val = "n/m" if t0.get("value") is None else f'{t0["value"]*100:.2f}%'
            lim = f'{t0.get("threshold",0)*100:.1f}%'
            passed = t0.get("pass")
            resp = Paragraph(f'<font color="{"#3B7A4B" if passed else "#B23B3B"}"><b>{"pass" if passed else "FAIL"}</b></font>', cell)
            rows.append([Paragraph(esc(lbl), cell), Paragraph(esc(t0.get("key", "")), cell),
                         Paragraph(val, cell), Paragraph(lim, cell), resp,
                         Paragraph(esc(clean_src(t0.get("source"))), cell)])
        t = Table(rows, colWidths=[1.85 * inch, 1.0 * inch, 0.7 * inch, 0.6 * inch, 0.6 * inch, 1.75 * inch], repeatRows=1)
        t.setStyle(tbl_style()); story.append(t)

    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "Generated by Foundry. This planning exhibit accompanies, and does not replace, the full "
        "results workbook. Figures are modeled projections, not a filed business plan.", small))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER, leftMargin=0.7 * inch, rightMargin=0.7 * inch,
                            topMargin=0.65 * inch, bottomMargin=0.6 * inch,
                            title=f"Executive Summary \u2014 {bank}")
    doc.build(story)
    return buf.getvalue()
