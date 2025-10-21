# app/routers/preflight.py
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import math

from app.schemas.panel_ir import PanelScheduleIR

router = APIRouter(prefix="/panel/preflight", tags=["panel-preflight"])

# -------------------------------
# Helpers
# -------------------------------

def _parse_voltage(v: str) -> dict:
    """
    Parse common voltage notations into line-to-line (V_LL) and line-to-neutral (V_LN).

    Accepts: "480/277V", "480Y/277", "208-120", "240V", "120/240 VAC", etc.
    Heuristic: when two numbers appear (A/B), treat A as V_LL and B as V_LN.
    """
    s = (v or "").upper().strip()
    # Strip common tokens and normalize separators
    for tok in ("VAC", "V", " VOLT", " VOLTS"):
        s = s.replace(tok, "")
    s = s.replace(" ", "")
    s = s.replace("-", "/")
    s = s.replace("Y", "")  # tolerate 480Y/277

    if "/" in s:
        a, b = s.split("/", 1)
        try:
            a = float(a); b = float(b)
            return {"V_LL": a, "V_LN": b}
        except Exception:
            return {"V_LL": None, "V_LN": None}
    else:
        try:
            a = float(s)
            return {"V_LL": a, "V_LN": None}
        except Exception:
            return {"V_LL": None, "V_LN": None}

def _phase_from_ir(ir: PanelScheduleIR) -> str:
    # IR validators normalize PHASE to "1PH" or "3PH"
    for p in ir.header.left_params:
        if p.name_text.upper() == "PHASE":
            return str(p.value or "").upper()
    return ""

def _voltage_from_ir(ir: PanelScheduleIR) -> dict:
    for p in ir.header.left_params:
        if p.name_text.upper() == "VOLTAGE":
            return _parse_voltage(str(p.value or ""))
    return {"V_LL": None, "V_LN": None}

def _wire_from_ir(ir: PanelScheduleIR) -> str:
    for p in ir.header.left_params:
        if p.name_text.upper() == "WIRE":
            return str(p.value or "").upper()
    return ""

def _neutral_from_ir(ir: PanelScheduleIR) -> str:
    for p in ir.header.right_params:
        if p.name_text.upper() == "NEUTRAL CONDUCTOR":
            return str(p.value or "").upper()
    return ""

def _infer_system_text(ir: PanelScheduleIR) -> str:
    """
    Lightweight inference of system topology text based on PHASE/WIRE/Voltage/Neutral.
    """
    phase = _phase_from_ir(ir)            # "1PH" or "3PH"
    wire  = _wire_from_ir(ir)             # "2W", "3W", "4W", etc.
    neu   = _neutral_from_ir(ir)          # e.g. "NONE", "COPPER", etc.
    V     = _voltage_from_ir(ir)
    V_LL, V_LN = V.get("V_LL"), V.get("V_LN")

    if phase == "1PH":
        # 3-wire split-phase if 120/240-ish or explicitly 3W
        if "3W" in wire or (V_LL and V_LN and abs(V_LL - 2*V_LN) < 3):
            return "SINGLE-PHASE, 3-WIRE (SPLIT-PHASE)"
        return "SINGLE-PHASE, 2-WIRE"

    if phase == "3PH":
        if "4W" in wire or V_LN:
            return "3PH WYE, GROUNDED"
        if "3W" in wire and ("NONE" in neu or not V_LN):
            return "3PH DELTA (LIKELY UNGROUNDED)"
        return "3PH (UNSPECIFIED TOPOLOGY)"

    return "UNKNOWN"

def _kva_formulas_per_phase(ir: PanelScheduleIR, system: Optional[str] = None) -> Dict[str, str]:
    """
    Build Excel formulas for per-phase kVA cells based on totals in G56/H56/I56.
    Writes formulas to G57/H57/I57, respectively.

      - 3PH WYE:    kVA_phase = V_LN * I_phase / 1000
      - 3PH DELTA:  per-line share ~ V_LL * I_line / (1000*SQRT(3))
      - 1PH 2-wire: kVA = V_use * I / 1000 (V_use = V_LL else V_LN)
      - 1PH 3-wire: per leg uses V_LN * I_leg / 1000

    We keep numbers literal (no uppercasing) so Excel parses them cleanly.
    """
    phase = _phase_from_ir(ir)
    V = _voltage_from_ir(ir)
    V_LL, V_LN = V.get("V_LL"), V.get("V_LN")
    system = system or _infer_system_text(ir)

    def fmt(v: Optional[float]) -> str:
        if v is None:
            return ""
        # Render integers without .0 for a clean formula
        return str(int(v)) if abs(v - int(v)) < 1e-9 else str(v)

    G56, H56, I56 = "G56", "H56", "I56"
    out: Dict[str, str] = {}

    if phase == "3PH":
        if "WYE" in system and V_LN:
            out["G57"] = f"={G56}*{fmt(V_LN)}/1000"
            out["H57"] = f"={H56}*{fmt(V_LN)}/1000"
            out["I57"] = f"={I56}*{fmt(V_LN)}/1000"
        elif "DELTA" in system and V_LL:
            out["G57"] = f"={G56}*{fmt(V_LL)}/(1000*SQRT(3))"
            out["H57"] = f"={H56}*{fmt(V_LL)}/(1000*SQRT(3))"
            out["I57"] = f"={I56}*{fmt(V_LL)}/(1000*SQRT(3))"
        else:
            # Unknown 3PH topology: prefer WYE model if we have V_LN, else Delta-share with V_LL
            if V_LN:
                out["G57"] = f"={G56}*{fmt(V_LN)}/1000"
                out["H57"] = f"={H56}*{fmt(V_LN)}/1000"
                out["I57"] = f"={I56}*{fmt(V_LN)}/1000"
            elif V_LL:
                out["G57"] = f"={G56}*{fmt(V_LL)}/(1000*SQRT(3))"
                out["H57"] = f"={H56}*{fmt(V_LL)}/(1000*SQRT(3))"
                out["I57"] = f"={I56}*{fmt(V_LL)}/(1000*SQRT(3))"
    else:
        # 1PH
        system_text = system or ""
        is_split = ("SPLIT" in system_text) or ("3-WIRE" in system_text)
        if is_split and V_LN:
            out["G57"] = f"={G56}*{fmt(V_LN)}/1000"
            out["H57"] = f"={H56}*{fmt(V_LN)}/1000"
            out["I57"] = f"={I56}*{fmt(V_LN)}/1000"
        else:
            V_use = V_LL or V_LN
            if V_use:
                out["G57"] = f"={G56}*{fmt(V_use)}/1000"
                out["H57"] = f"={H56}*{fmt(V_use)}/1000"
                out["I57"] = f"={I56}*{fmt(V_use)}/1000"

    return out

def _balance_expected(ir: PanelScheduleIR) -> bool:
    # Expect balance on 3PH panels by default
    return _phase_from_ir(ir) == "3PH"

def _balance_measured(ir: PanelScheduleIR) -> Optional[bool]:
    # We don’t read sheet values here; treat balance as “unknown” in preflight.
    # (If you later compute G56/H56/I56 before preflight, you could pass those in.)
    return None

def _to_amps(val: Optional[str]) -> Optional[float]:
    """
    Parse strings like '225A', '225 A', '225' into a float (amps).
    Return None on failure.
    """
    if val is None:
        return None
    s = str(val).upper().replace("A", "").strip()
    try:
        return float(s)
    except Exception:
        return None

# -------------------------------
# Response models
# -------------------------------

class QAItem(BaseModel):
    check: str
    pass_: bool = Field(..., alias="pass")
    notes: Optional[str] = None

class GPTPreflightResponse(BaseModel):
    system: str
    line_voltage: Optional[float] = None
    phase_voltage: Optional[float] = None
    balance_expected: bool
    balance_measured: Optional[bool] = None
    items: List[QAItem]
    warnings: List[str]
    formulas: Dict[str, str]  # e.g. {"G57":"=G56*277/1000", ...}

# -------------------------------
# Route (canonical)
# -------------------------------

@router.post("/gpt", response_model=GPTPreflightResponse)
def preflight_gpt(ir: PanelScheduleIR):
    """
    Canonical GPT preflight endpoint.
    IMPORTANT: If you previously exposed /panel/preflight/gpt elsewhere (e.g. panel.py),
    remove/disable that one to avoid route collisions.
    """
    # Deterministic inference first (fast + reliable)
    V = _voltage_from_ir(ir)
    system = _infer_system_text(ir)
    formulas = _kva_formulas_per_phase(ir, system=system)

    items: List[QAItem] = []
    warnings: List[str] = []

    # MCB vs BUS sanity check (warning only)
    main_bus = None
    main_cb: Optional[float | str] = None

    for p in ir.header.left_params:
        label = p.name_text.upper()
        if label == "MAIN BUS AMPS":
            main_bus = _to_amps(p.value if p.value is not None else None)
        elif label == "MAIN CIRCUIT BREAKER":
            val = str(p.value or "").upper().strip()
            if val == "MLO":
                main_cb = "MLO"
            else:
                main_cb = _to_amps(val)

    if isinstance(main_cb, float) and isinstance(main_bus, float) and main_cb > main_bus:
        warnings.append("WARNING: MAIN CIRCUIT BREAKER IS LARGER THAN MAIN BUS AMPS.")
        items.append(QAItem.model_validate({"check": "MCB <= BUS AMPACITY", "pass": False, "notes": f"MCB {main_cb}A > Bus {main_bus}A"}))
    else:
        items.append(QAItem.model_validate({"check": "MCB <= BUS AMPACITY (or MLO)", "pass": True}))

    # (Optional) This is where you'd call OpenAI to refine/augment `system`, `items`, `warnings`.
    # Keep the deterministic results as defaults; merge GPT notes if you add that later.

    return GPTPreflightResponse(
        system=system,
        line_voltage=V.get("V_LL"),
        phase_voltage=V.get("V_LN"),
        balance_expected=_balance_expected(ir),
        balance_measured=_balance_measured(ir),
        items=items,
        warnings=warnings,
        formulas=formulas,
    )