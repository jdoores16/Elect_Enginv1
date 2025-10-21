

# v4 standards helper
from app.schemas.standards import StandardsConfig
from pathlib import Path as _Path
import json as _json

def _load_standards() -> StandardsConfig:
    here = _Path(__file__).resolve().parents[1]
    cfg_path = here / "standards" / "active.json"
    if cfg_path.exists():
        try:
            return StandardsConfig(**_json.loads(cfg_path.read_text()))
        except Exception:
            pass
    return StandardsConfig()

def _ensure_layer(doc, name: str, color: int = 7):
    if name not in doc.layers:
        doc.layers.new(name=name)
        try:
            doc.layers.get(name).color = color
        except Exception:
            pass
import ezdxf
from app.utils.dxf_blocks import import_dxf_as_block, insert_block
from ezdxf.enums import TextEntityAlignment
from pathlib import Path
from app.schemas.models import PlanRequest

def generate_power_plan_dxf(req: PlanRequest, out_path: Path):
    doc = ezdxf.new(dxfversion="R2010")
    msp = doc.modelspace()

# -- standards --
cfg = _load_standards()
lyr_ann = cfg.layers.get('annotations', 'E-ANNO-TEXT'); _ensure_layer(doc, lyr_ann)

## v5 titleblock+symbols
# Titleblock insertion (if configured)
if cfg.titleblock:
    tb_path = (_Path(__file__).resolve().parents[1] / "standards" / cfg.titleblock) if not _Path(cfg.titleblock).is_absolute() else _Path(cfg.titleblock)
    if tb_path.exists():
        try:
            blk_name = tb_path.stem
            import_dxf_as_block(doc, tb_path, blk_name)
            insert_block(msp, blk_name, insert=(0,0), layer=lyr_ann)
        except Exception:
            # non-fatal
            pass

# Symbols mapping (optional); CAD modules can call helper to place by tag prefix
def _symbol_for(tag: str) -> str | None:
    mapping = (cfg.symbols or {})
    t = (tag or "").lower()
    # simple heuristics by prefix
    if t.startswith("rec") or t.startswith("r-"):
        return mapping.get("receptacle")
    if t.startswith("l") or "lum" in t:
        return mapping.get("luminaire")
    if "panel" in t or t.startswith("pnl") or t.startswith("panel"):
        return mapping.get("panel")
    if t.startswith("s") and ("switch" in t or len(t) <= 3):
        return mapping.get("switch")
    return None
lyr_rooms = cfg.layers.get('rooms', 'E-ANNO-ROOM'); _ensure_layer(doc, lyr_rooms)
lyr_power_devices = cfg.layers.get('power_devices', 'E-POWR-DEV'); _ensure_layer(doc, lyr_power_devices)


    msp.add_text(f"{req.project} - Power Plan", dxfattribs={"height":0.3, "layer":lyr_ann}).set_pos((0,7), align=TextEntityAlignment.LEFT)

    for r in req.rooms:
        msp.add_lwpolyline([(r.x,r.y),(r.x+r.w,r.y),(r.x+r.w,r.y+r.h),(r.x,r.y+r.h),(r.x,r.y)], dxfattribs={"closed": True, "layer":lyr_rooms})
        msp.add_text(r.name, dxfattribs={"height":0.15, "layer":lyr_ann}).set_pos((r.x+0.1, r.y+r.h-0.2))

    for d in req.devices:
        msp.add_circle((d.x,d.y), radius=0.06, dxfattribs={"layer":lyr_power_devices})
        msp.add_text(d.tag, dxfattribs={"height":0.12, "layer":lyr_ann}).set_pos((d.x+0.1, d.y-0.05))

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(out_path)