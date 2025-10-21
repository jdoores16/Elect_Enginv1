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
from app.utils.dxf_blocks import import_dxf_as_block, insert_block

logger = logging.getLogger(__name__)


# -- standards loader ---------------------------------------------------------
def _load_standards() -> StandardsConfig:
    here = Path(__file__).resolve().parents[1]  # repo root candidate
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
    """Use set_pos if available; otherwise set insertion point directly."""
    if hasattr(ent, "set_pos"):
        ent.set_pos(pos, align=align)
    else:
        ent.dxf.insert = pos  # LEFT align fallback


# -- optional symbol resolver -------------------------------------------------
def _symbol_for(tag: Optional[str], cfg: StandardsConfig) -> Optional[str]:
    mapping = (cfg.symbols or {})
    t = (tag or "").lower()
    if t.startswith("rec") or t.startswith("r-"):
        return mapping.get("receptacle")
    if t.startswith("l") or "lum" in t:
        return mapping.get("luminaire")
    if "panel" in t or t.startswith("pnl"):
        return mapping.get("panel")
    if t.startswith("s") and ("switch" in t or len(t) <= 3):
        return mapping.get("switch")
    return None


# -- main generator -----------------------------------------------------------
def generate_power_plan_dxf(req: PlanRequest, out_path: Path) -> Path:
    """
    Build a simple power plan:
      - Draw rooms as closed polylines
      - Mark devices with circles + text tags
      - Optionally insert a titleblock
      - Add a sheet/title note
    """
    out_path = Path(out_path)

    # New DXF document
    doc = ezdxf.new(dxfversion="R2010")
    msp = doc.modelspace()

    # -- standards ------------------------------------------------------------
    cfg = _load_standards()

    # Layers
    lyr_ann = cfg.layers.get("annotations", "E-ANNO-TEXT"); _ensure_layer(doc, lyr_ann)
    lyr_rooms = cfg.layers.get("rooms", "E-ANNO-ROOM"); _ensure_layer(doc, lyr_rooms)
    lyr_power_devices = cfg.layers.get("power_devices", "E-POWR-DEV"); _ensure_layer(doc, lyr_power_devices)

    ## v5 titleblock+symbols --------------------------------------------------
    if cfg.titleblock:
        tb_path = (
            Path(__file__).resolve().parents[1] / "standards" / cfg.titleblock
            if not Path(cfg.titleblock).is_absolute()
            else Path(cfg.titleblock)
        )
        if tb_path.exists():
            try:
                blk_name = tb_path.stem
                import_dxf_as_block(doc, tb_path, blk_name)
                insert_block(msp, blk_name, insert=(0, 0), layer=lyr_ann)
            except Exception:
                # non-fatal
                pass

    # -- title / sheet note ---------------------------------------------------
    project_title = getattr(req, "project", "Project")
    _place_text(
        msp.add_text(f"{project_title} - Power Plan", dxfattribs={"height": 0.3, "layer": lyr_ann}),
        (0, 7),
        align=TextEntityAlignment.LEFT,
    )

    # -- rooms ----------------------------------------------------------------
    for r in (getattr(req, "rooms", []) or []):
        msp.add_lwpolyline(
            [
                (r.x, r.y),
                (r.x + r.w, r.y),
                (r.x + r.w, r.y + r.h),
                (r.x, r.y + r.h),
                (r.x, r.y),
            ],
            dxfattribs={"closed": True, "layer": lyr_rooms},
        )
        _place_text(
            msp.add_text(r.name, dxfattribs={"height": 0.15, "layer": lyr_ann}),
            (r.x + 0.1, r.y + r.h - 0.2),
            align=TextEntityAlignment.LEFT,
        )

    # -- devices --------------------------------------------------------------
    for d in (getattr(req, "devices", []) or []):
        msp.add_circle((d.x, d.y), radius=0.06, dxfattribs={"layer": lyr_power_devices})
        tag = getattr(d, "tag", "") or "DEV"
        _place_text(
            msp.add_text(tag, dxfattribs={"height": 0.12, "layer": lyr_ann}),
            (d.x + 0.1, d.y - 0.05),
            align=TextEntityAlignment.LEFT,
        )

    # -- save -----------------------------------------------------------------
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(out_path)
    return out_path