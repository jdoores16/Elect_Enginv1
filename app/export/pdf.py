from __future__ import annotations
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from app.schemas.panel_ir import PanelScheduleIR

def export_pdf_from_ir(ir: PanelScheduleIR, out_pdf: str) -> str:
    c = canvas.Canvas(out_pdf, pagesize=letter)
    width, height = letter

    # Title
    c.setFont("Helvetica-Bold", 14)
    c.drawString(0.75*inch, height - 0.9*inch, f"Panel Schedule: {ir.header.panel_name}")

    # Normalize phase label for text output
    for p in ir.header.left_params:
        if p.name_text.strip().upper() == "PHASE" and isinstance(p.value, str):
            p.value = p.value.replace("Ø", "").replace("O", "").replace("PHASE", "").strip().upper()
            if not p.value.endswith("PH"):
                p.value += "PH"

    # Header pairs (left / right columns)
    c.setFont("Helvetica", 9)
    y_left = height - 1.15*inch
    for pair in ir.header.left_params:
        val = "" if pair.value is None else str(pair.value)
        c.drawString(0.75*inch, y_left, f"{pair.name_text}: {val}")
        y_left -= 12

    y_right = height - 1.15*inch
    for pair in ir.header.right_params:
        val = "" if pair.value is None else str(pair.value)
        c.drawString(3.9*inch, y_right, f"{pair.name_text}: {val}")
        y_right -= 12

    y = min(y_left, y_right) - 16

    # Circuits header
    c.setFont("Helvetica-Bold", 10)
    c.drawString(0.75*inch, y, "Circuits (summary)")
    y -= 14
    c.setFont("Helvetica", 8)
    c.drawString(0.75*inch, y, "CKT  SIDE  ROW  POLES  BRKR_A  LOAD_A  PH[A,B,C]  DESCRIPTION")
    y -= 10
    c.line(0.75*inch, y, width - 0.75*inch, y)
    y -= 8

    # Rows
    def phases(rec) -> str:
        return "".join(ch for ch, flag in zip("ABC", [rec.phA, rec.phB, rec.phC]) if flag)

    for rec in sorted(ir.circuits, key=lambda r: r.ckt):
        if y < 1.0*inch:
            c.showPage()
            y = height - 0.9*inch
            c.setFont("Helvetica", 8)

        phs = phases(rec)
        poles = "" if rec.poles is None else str(rec.poles)
        c.drawString(
            0.75*inch, y,
            f"{rec.ckt:<4} {rec.side:<4} {rec.excel_row:<3} {poles:<5} "
            f"{int(rec.breaker_amps):<6} {int(rec.load_amps):<6} {phs:<7} {rec.description or ''}"
        )
        y -= 10

    c.setFont("Helvetica-Oblique", 7)
    c.drawString(0.75*inch, 0.6*inch, "Draft – verify per current NEC and local AHJ before issuance.")
    c.save()
    return out_pdf