# app/ai/checklist.py
from __future__ import annotations
from typing import List, Dict, Any
from app.schemas.panel_ir import PanelScheduleIR, NameValuePair

def _get_left(ir: PanelScheduleIR, label: str) -> str:
    for p in ir.header.left_params:
        if p.name_text.strip().upper() == label.upper():
            return "" if p.value is None else str(p.value)
    return ""

def build_checklist(ir: PanelScheduleIR) -> List[str]:
    """Deterministic checks we want GPT to answer Yes/No with notes."""
    voltage = _get_left(ir, "VOLTAGE")
    phase   = _get_left(ir, "PHASE")
    wire    = _get_left(ir, "WIRE")
    main_bus = _get_left(ir, "MAIN BUS AMPS")
    mcb      = _get_left(ir, "MAIN CIRCUIT BREAKER")

    checks = [
        "Header text matches template labels (no labels overwritten).",
        f"PHASE value normalized (expected '1PH' or '3PH'): got '{phase}'.",
        f"WIRE format is reasonable (e.g., '3W+G' or '4W+G'): got '{wire}'.",
        f"VOLTAGE format is reasonable (e.g., '208/120V' or '480Y/277V'): got '{voltage}'.",
        "All required header values present (left and right blocks; O9 blank).",
        "Sheet/tab title matches 'VOLTAGE, PHASE, WIRE' rule and within Excel 31-char limit.",
        "Rows 10–11 untouched; G..I columns (12–53) untouched.",
        "Each circuit’s pole count matches phases set (1, 2, or 3).",
        "Circuit description length ≤ 39 characters post-trim/uppercase.",
        "Phase load written only to the correct slot per circuit number (A for 1–2, B for 3–4, C for 5–6, and so on).",
        "Breaker_amps and load_amps are both present and not equal.",
        "No duplicate circuit numbers; row mapping correct (ckt→row).",
        "Left/right header alignment keeps merged label cells right-justified.",
    ]
    # The engineering sanity we already enforce, but we want GPT to state it plainly:
    if mcb == "MLO":
        checks.append("Since panel is MLO, main bus amps vs. main breaker comparison is not applicable.")
    else:
        checks.append(f"Verify MAIN CIRCUIT BREAKER ( '{mcb}' ) is not larger than MAIN BUS AMPS ( '{main_bus}' ).")

    return checks

def summarize_for_gpt(ir: PanelScheduleIR) -> str:
    """Compact, human-readable dump for GPT. (We don’t expose entire XLSX here.)"""
    def fmt_pair(p: NameValuePair) -> str:
        return f"- {p.name_text}: {p.value if p.value is not None else ''}"

    left = "\n".join(fmt_pair(p) for p in ir.header.left_params)
    right = "\n".join(fmt_pair(p) for p in ir.header.right_params)

    lines = [
        f"# PANEL HEADER",
        f"Panel Name: {ir.header.panel_name}",
        "## Left params:",
        left,
        "## Right params:",
        right,
        "",
        "# CIRCUITS (first 20 shown, sorted):",
    ]
    for rec in sorted(ir.circuits, key=lambda x: x.ckt)[:20]:
        phs = "".join(ch for ch, val in zip("ABC", [rec.phA, rec.phB, rec.phC]) if val)
        lines.append(
            f"- CKT {rec.ckt:>2} | side={rec.side} row={rec.excel_row} "
            f"poles={rec.poles or ''} breaker={rec.breaker_amps} load={rec.load_amps} "
            f"ph={phs or ''} desc='{rec.description or ''}'"
        )
    if len(ir.circuits) > 20:
        lines.append(f"... ({len(ir.circuits)-20} more circuits not shown here)")
    return "\n".join(lines)