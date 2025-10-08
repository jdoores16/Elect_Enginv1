
# v4 standards helper
from __future__ import annotations

from pathlib import Path
import json as _json
import logging
from typing import Optional

import ezdxf
from ezdxf.enums import TextEntityAlignment
from pydantic import ValidationError

from app.schemas.models import PlanRequest
from app.schemas.standards import StandardsConfig

logger = logging.getLogger(__name__)


# -- standards loader ---------------------------------------------------------
def _load_standards() -> StandardsConfig:
    here = Path(__file__).resolve().parents[1]
    cfg_path = here / "standards" / "active.json"
    if cfg_path.exists():
        try:
            return StandardsConfig(**_json.loads(cfg_path.read_text(encoding="utf-8")))
        except _json.JSONDecodeError as e:
            logger.warning(f"Standards file is not valid JSON: {cfg_path}. Error: {e}. Using defaults.")
        except ValidationError as e:
            logger.warning(f"Standards file does not match expected schema: {cfg_path}. Error: {e}. Using defaults.")
        except Exception as e:
            logger.error(f"Unexpected error loading standards from {cfg_path}: {e}. Using defaults.")
    return StandardsConfig()


# -- layer helper -------------------------------------------------------------
def _ensure_layer(doc: ezdxf.EzDxf, name: str, color: int = 7):
    if name not in doc.layers:
        doc.layers.add(name=name)
        try:
            doc.layers.get(name).color = color
        except Exception:
            pass


# -- text placement (ezdxf version-safe) -------------------------------------
def _place_text(ent, pos, align=TextEntityAlignment.LEFT):
    if hasattr(ent, "set_pos"):
        ent.set_pos(pos, align=align)
    else:
        ent.dxf.insert = pos


# -- utilities ----------------------------------------------------------------
def _is_panelish(tag: str) -> bool:
    t = (tag or "").upper()
    return (
        t.startswith("P") or
        "PANEL" in t or
        "MCC" in t or
        "SWBD" in t or
        "SWGR" in t or
        "MSB" in t
    )


def _draw_box(msp, x: float, y: float, w: float, h: float, layer: str):
    msp.add_lwpolyline([(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)], dxfattribs={"closed": True, "layer": layer})


def _label(msp, text: str, pos: tuple[float, float], layer: str, height: float = 0.12):
    ent = msp.add_text(text, dxfattribs={"height": height, "layer": layer})
    _place_text(ent, pos, align=TextEntityAlignment.LEFT)


# -- main generator -----------------------------------------------------------
def generate_one_line_dxf(req: PlanRequest, out_path: Path) -> Path:
    """
    Minimal one-line diagram:
      - Service source (utility) feeding Main Switchboard
      - Panels inferred from req.devices[*].tag arranged vertically and fed from MSB
      - Simple feeders as lines
    """
    out_path = Path(out_path)

    doc = ezdxf.new(dxfversion="R2010")
    msp = doc.modelspace()

    # -- standards ------------------------------------------------------------
    cfg = _load_standards()

    lyr_ann = cfg.layers.get("annotations", "E-ANNO-TEXT"); _ensure_layer(doc, lyr_ann)
    lyr_bus = cfg.layers.get("one_line_bus", "E-POWR-1L-BUS"); _ensure_layer(doc, lyr_bus)
    lyr_equip = cfg.layers.get("one_line_equip", "E-POWR-1L-EQ"); _ensure_layer(doc, lyr_equip)
    lyr_feeder = cfg.layers.get("one_line_feeder", "E-POWR-1L-FDR"); _ensure_layer(doc, lyr_feeder)

    # -- title ----------------------------------------------------------------
    project_title = getattr(req, "project", "Project")
    _label(msp, f"{project_title} - One-Line Diagram", (0, 7), lyr_ann, height=0.30)

    # -- service + main -------------------------------------------------------
    # Utility/Service
    _draw_box(msp, -2.0, 5.0, 1.8, 0.8, lyr_equip)
    _label(msp, "UTILITY", (-1.9, 5.1), lyr_ann)
    # Riser to MSB
    msp.add_line((-1.1, 5.0), (0.0, 4.2), dxfattribs={"layer": lyr_feeder})
    # Main Switchboard (MSB/SWGR)
    _draw_box(msp, 0.0, 3.7, 2.6, 1.4, lyr_equip)
    _label(msp, "MSB", (0.2, 4.6), lyr_ann)

    # -- panels from devices --------------------------------------------------
    panels: list[str] = []
    for d in (getattr(req, "devices", []) or []):
        tag = getattr(d, "tag", "")
        if tag and _is_panelish(tag):
            panels.append(tag.upper())

    if not panels:
        panels = ["PANEL L1", "PANEL L2"]

    # Place panels vertically and connect feeders from MSB
    x0 = 1.3
    y_start = 3.5
    spacing = 1.2
    for i, p in enumerate(panels):
        y = y_start - i * spacing
        # Feeder line
        msp.add_line((x0 + 1.3, 4.0), (x0 + 3.3, y + 0.25), dxfattribs={"layer": lyr_feeder})
        # Panel box
        _draw_box(msp, x0 + 3.3, y, 2.2, 0.5, lyr_equip)
        _label(msp, p, (x0 + 3.45, y + 0.1), lyr_ann)

    # -- save -----------------------------------------------------------------
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(out_path)
    return out_path