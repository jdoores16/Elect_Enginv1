from __future__ import annotations
from typing import List, Literal, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator
import re

Scalar = Union[str, float, int, bool, None]

LEFT_LABELS = [
    ("A2", "B2", "VOLTAGE"),
    ("A3", "B3", "PHASE"),
    ("A4", "B4", "WIRE"),
    ("A5", "B5", "MAIN BUS AMPS"),
    ("A6", "B6", "MAIN CIRCUIT BREAKER"),
    ("A7", "B7", "MOUNTING"),
    ("A8", "B8", "FEED"),
    ("A9", "B9", "FEED-THRU LUGS"),
]

RIGHT_LABELS = [
    ("I2:N2", "O2", "LOCATION"),
    ("I3:N3", "O3", "FED FROM"),
    ("I4:N4", "O4", "UL LISTED EQUIPMENT SHORT CIRCUIT RATING"),
    ("I5:N5", "O5", "MAXIMUM AVAILABLE SHORT CIRCUIT CURRENT"),
    ("I6:N6", "O6", "PHASE CONDUCTOR"),
    ("I7:N7", "O7", "NEUTRAL CONDUCTOR"),
    ("I8:N8", "O8", "GROUND CONDUCTOR"),
]

class NameValuePair(BaseModel):
    name_cell: str
    value_cell: str
    name_text: str
    value: Scalar | None = None

    # Pydantic v2 style; strip whitespace on strings
    model_config = {"str_strip_whitespace": True}

    # Force any textual value to ALL CAPS
    @field_validator("value")
    @classmethod
    def _to_upper(cls, v):
        if isinstance(v, str):
            return v.strip().upper()
        return v

class HeaderBlock(BaseModel):
    panel_name_cell: Literal["A1:O1"] = "A1:O1"
    panel_name: str

    left_params: List[NameValuePair] = Field(..., min_items=8, max_items=8)
    right_params: List[NameValuePair] = Field(..., min_items=7, max_items=7)

    right_unused_value_cell: Literal["O9"] = "O9"
    right_unused_value: Optional[str] = None

    @staticmethod
    def _normalize_mcb_value(raw: Union[str, float, int, bool, None]) -> str:
        """
        Normalize MAIN CIRCUIT BREAKER value.
        - Any phrasing indicating 'not MCB' or 'MLO' -> 'MLO'
        - A numeric with/without 'A' -> '<amps>A'
        - Otherwise default to 'MLO'
        """
        if raw is None:
            return "MLO"

        s = str(raw).strip().upper()

        mlo_hints = (
            "MLO", "MAIN LUG", "MAIN LUGS", "LUGS ONLY",
            "NO MAIN", "NO MCB", "NOT MCB", "NOT A MCB", "NOT A MCB PANEL",
            "NOT BREAKER", "MAIN LUG ONLY"
        )
        if any(h in s for h in mlo_hints):
            return "MLO"

        if "NOT" in s and ("MCB" in s or "MAIN" in s or "BREAKER" in s):
            return "MLO"

        m = re.search(r"(\d+)\s*A?\b", s)
        if m:
            amps = int(m.group(1))
            return f"{amps}A"

        if "MCB" in s or "BREAKER" in s:
            return "MLO"

        return "MLO"

    @staticmethod
    def _normalize_phase_value(raw: Union[str, float, int, bool, None]) -> str:
        """
        Normalize PHASE to '1PH' or '3PH' from inputs like '1Ø', '1 O', 'SINGLE', '3Ø', 'THREE PHASE', etc.
        """
        if raw is None:
            return ""
        s = str(raw).strip().upper()
        # remove common glyphs/words
        s = s.replace("Ø", "").replace("PHASE", "").replace("PH", "").replace("O", "").strip()
        # map common words
        if s in {"SINGLE", "SINGLE-", "SINGLE PH", "1", "1-"}:
            return "1PH"
        if s in {"THREE", "THREE-", "THREE PH", "3", "3-"}:
            return "3PH"
        # numeric-first fallback
        if s.startswith("1"):
            return "1PH"
        if s.startswith("3"):
            return "3PH"
        # unknown -> empty (writer will handle)
        return "1PH" if "SINGLE" in s else ("3PH" if "THREE" in s else s)

    @field_validator("left_params")
    @classmethod
    def _enforce_left(cls, items: List[NameValuePair]) -> List[NameValuePair]:
        for (exp_name_cell, exp_val_cell, exp_text), item in zip(LEFT_LABELS, items):
            if item.name_cell.upper() != exp_name_cell:
                raise ValueError(f"Left label cell must be {exp_name_cell}, got {item.name_cell}")
            if item.value_cell.upper() != exp_val_cell:
                raise ValueError(f"Left value cell must be {exp_val_cell}, got {item.value_cell}")
            if item.name_text.strip().upper() != exp_text:
                raise ValueError(f"Left label text must be '{exp_text}', got '{item.name_text}'")

            # Normalize MAIN CIRCUIT BREAKER
            if exp_text == "MAIN CIRCUIT BREAKER":
                item.value = cls._normalize_mcb_value(item.value)

            # Normalize PHASE -> 1PH/3PH
            if exp_text == "PHASE":
                item.value = cls._normalize_phase_value(item.value)

        return items

    @field_validator("right_params")
    @classmethod
    def _enforce_right(cls, items: List[NameValuePair]) -> List[NameValuePair]:
        for (exp_name_cell, exp_val_cell, exp_text), item in zip(RIGHT_LABELS, items):
            if item.name_cell.upper() != exp_name_cell:
                raise ValueError(f"Right label cell must be {exp_name_cell}, got {item.name_cell}")
            if item.value_cell.upper() != exp_val_cell:
                raise ValueError(f"Right value cell must be {exp_val_cell}, got {item.value_cell}")
            if item.name_text.strip().upper() != exp_text:
                raise ValueError(f"Right label text must be '{exp_text}', got '{item.name_text}'")
        return items

    @field_validator("right_unused_value")
    @classmethod
    def _unused_blank(cls, v: Optional[str]) -> Optional[str]:
        if v not in (None, "", " "):
            raise ValueError("O9 must remain blank (unused).")
        return v

class CircuitRecord(BaseModel):
    ckt: int = Field(..., ge=1, le=84)
    side: Literal["odd", "even"]
    excel_row: int = Field(..., ge=12, le=53)

    # NEW: distinct values
    breaker_amps: float = Field(..., ge=0)   # goes to F (odd) / J (even)
    load_amps: float = Field(..., ge=0)      # goes to phase slot (B/C/D or L/M/N)
    poles: Optional[int] = Field(None, ge=1, le=3)
    phA: Optional[bool] = None
    phB: Optional[bool] = None
    phC: Optional[bool] = None
    description: Optional[str] = None
    load_type: Optional[Literal["LTG", "RCP", "MTR", "C", "NC"]] = Field(
        None, 
        description="Load type: LTG=Lighting, RCP=Receptacle, MTR=Motor, C=Continuous, NC=Non-Continuous"
    )

    @field_validator("ckt")
    @classmethod
    def _parity(cls, v: int, info) -> int:
        side = info.data.get("side")
        if side == "odd" and v % 2 == 0:
            raise ValueError("Odd side must contain odd circuit numbers.")
        if side == "even" and v % 2 != 0:
            raise ValueError("Even side must contain even circuit numbers.")
        return v

    @field_validator("poles")
    @classmethod
    def _ph_consistency(cls, v: Optional[int], info) -> Optional[int]:
        if v is None:
            return v
        ph_count = sum(bool(info.data.get(k)) for k in ("phA", "phB", "phC"))
        if ph_count and ph_count != v:
            raise ValueError(f"poles={v} but {ph_count} phases set True.")
        return v
    
    @model_validator(mode="after")
    def _breaker_vs_load(self):
        eps = 1e-6
        if self.breaker_amps is None or self.load_amps is None:
            raise ValueError("Both breaker_amps and load_amps are required.")
        if abs(self.breaker_amps - self.load_amps) <= eps:
            raise ValueError("breaker_amps must not equal load_amps.")
        return self
    
    @field_validator("description")
    @classmethod
    def limit_description_length(cls, v):
        if v is None:
            return v
        v = v.strip().upper()
        if len(v) > 39:
            v = v[:39]
        return v

class PanelScheduleIR(BaseModel):
    version: str = "1.0.0"
    header: HeaderBlock
    circuits: List[CircuitRecord]

    @field_validator("circuits")
    @classmethod
    def _circuit_rules(cls, items: List[CircuitRecord]) -> List[CircuitRecord]:
        seen: set[int] = set()
        for c in items:
            if c.ckt in seen:
                raise ValueError(f"Duplicate circuit {c.ckt}")
            seen.add(c.ckt)
            expected_row = 11 + ((c.ckt + 1) // 2)  # rows 12..53
            if c.excel_row != expected_row:
                raise ValueError(f"Circuit {c.ckt} must be on row {expected_row}, not {c.excel_row}.")
        return items