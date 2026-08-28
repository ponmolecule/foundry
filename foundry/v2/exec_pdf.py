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

    import re as _re
    def boldmd(s):
        # escape first (safe), then turn **...** into reportlab's <b> so the metric renders bold
        return _re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", esc(s))

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
                         Paragraph(boldmd(f.get("text", "")), cell)])
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
            obs = boldmd(m.get("text", ""))
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

    # ---- Reasonableness bands in effect (the standards inputs were judged against) ----
    try:
        from .challenge_q import CHALLENGE_THRESHOLDS
        from .peer_calibration import _flag_client_value
        ta = (res.get("financials", {}).get("bs", {}).get("totalAssets") or [0])[-1] or 0
        brows = [dict(x) for x in CHALLENGE_THRESHOLDS]
        peer_tier = False
        if ta and ta > 0:
            try:
                from .peer_calibration import calibrate_thresholds
                brows, _prov = calibrate_thresholds(CHALLENGE_THRESHOLDS, ta)
                peer_tier = True
            except Exception:
                peer_tier = False
        if brows:
            story.append(Paragraph("Reasonableness bands in effect", h3))
            story.append(Paragraph("The standards these inputs were judged against \u2014 rule, trigger, "
                                   "the peer band where resolved, and the model's tested value.", introS))
            if peer_tier:
                head = hdr("ID", "Rule", "Trigger", "Peer band (p10\u00b7med\u00b7p90)", "Your plan")
                cw = [0.85 * inch, 1.55 * inch, 1.5 * inch, 1.5 * inch, 0.75 * inch]
            else:
                head = hdr("ID", "Rule", "Trigger", "Your plan")
                cw = [0.9 * inch, 2.1 * inch, 2.65 * inch, 0.85 * inch]
            brow_cells = [head]
            for x in brows:
                rid = x.get("id", "")
                try:
                    v = _flag_client_value({"id": rid}, cfg)
                except Exception:
                    v = None
                planv = "\u2014" if v is None else f"{round(float(v),2)}%"
                base_cells = [Paragraph(esc(rid), cell), Paragraph(esc(x.get("rule", "")), cell),
                              Paragraph(esc(x.get("trigger", "")), cell)]
                if peer_tier:
                    p = x.get("peer")
                    band = (f'{float(p["p10"]):.2f}\u00b7{float(p["p50"]):.2f}\u00b7{float(p["p90"]):.2f}'
                            f'<br/><font color="#6E7C93" size="7">{esc(p.get("vintage",""))} \u00b7 n={p.get("n","")}</font>') if p else esc(x.get("peer_note", "structural"))
                    base_cells.append(Paragraph(band, cell))
                base_cells.append(Paragraph(planv, cell))
                brow_cells.append(base_cells)
            t = Table(brow_cells, colWidths=cw, repeatRows=1)
            t.setStyle(tbl_style()); story.append(t)
    except Exception:
        pass  # bands are supplementary; never let them break the exhibit

    # ---- Three-year financial summary ----
    qstats = res.get("quick_stats")
    if qstats and qstats.get("rows"):
        story.append(Paragraph("Three-year financial summary", h3))
        if qstats.get("note"):
            story.append(Paragraph(esc(qstats["note"]) + ".", introS))
        rows = [hdr("", "Year 1", "Year 2", "Year 3")]
        for x in qstats["rows"]:
            yvals = []
            for v in (x.get("y") or []):
                if v is None:
                    yvals.append(Paragraph("\u2014", cell))
                else:
                    col = "#B23B3B" if (isinstance(v, (int, float)) and v < 0) else "#1D2735"
                    yvals.append(Paragraph(f'<font color="{col}">{v:,.2f}</font>', cell))
            while len(yvals) < 3:
                yvals.append(Paragraph("\u2014", cell))
            rows.append([Paragraph(esc(x.get("label", "")), cell)] + yvals[:3])
        t = Table(rows, colWidths=[2.9 * inch, 1.4 * inch, 1.4 * inch, 1.4 * inch], repeatRows=1)
        t.setStyle(tbl_style()); story.append(t)

    # ---- Model checks — integrity and viability are DIFFERENT questions, each under its own header:
    #      integrity = does the arithmetic hold together; viability = does the plan clear its commitments.
    checks = res.get("checks")
    if checks and checks.get("rows"):
        story.append(Paragraph("Model checks \u2014 " + esc(checks.get("master", "")), h3))
        if checks.get("doctrine"):
            story.append(Paragraph(esc(checks["doctrine"]) + ".", introS))
        h4 = ParagraphStyle("H4", parent=body, fontName="Helvetica-Bold", fontSize=9.5,
                            textColor=NAVY, spaceBefore=6, spaceAfter=2)
        _CLASS_LABEL = {
            "integrity": ("Integrity checks", "Does the arithmetic hold together \u2014 balance-sheet identities, accounting ties."),
            "viability": ("Viability checks", "Does the modeled bank clear its commitments \u2014 capital, leverage, going-concern."),
            "notice": ("Notices", "Facts about the projection worth an examiner's attention \u2014 not a viability verdict."),
        }
        for kl in ("integrity", "viability", "notice"):
            krows = [r0 for r0 in checks["rows"] if r0.get("class") == kl]
            if not krows:
                continue
            title, blurb = _CLASS_LABEL.get(kl, (kl.title() + " checks", ""))
            story.append(Paragraph(title, h4))
            if blurb:
                story.append(Paragraph(blurb, introS))
            rows = [hdr("Result", "Check", "Note")]
            for x in krows:
                passed = x.get("pass")
                rp = Paragraph(f'<font color="{"#3B7A4B" if passed else "#B23B3B"}"><b>{"PASS" if passed else "FAIL"}</b></font>', cell)
                rows.append([rp, Paragraph(esc(x.get("label", "")), cell),
                             Paragraph(esc(x.get("note", "")), cell)])
            t = Table(rows, colWidths=[0.7 * inch, 3.1 * inch, 2.7 * inch], repeatRows=1)
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
