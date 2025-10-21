

# app/cad/one_line.py
import json as _json
from pathlib import Path, Path as _Path
from typing import Optional

import ezdxf
from ezdxf.enums import TextEntityAlignment

from app.schemas.models import OneLineRequest
from app.schemas.standards import StandardsConfig
from app.utils.dxf_blocks import import_dxf_as_block, insert_block


# ---------- standards helpers ----------
def _load_standards() -> StandardsConfig:
    here = _Path(__file__).resolve().parents[1]
    cfg_path = here / "standards" / "active.json"
    if cfg_path.exists():
        try:
            return StandardsConfig(**_json.loads(cfg_path.read_text()))
        except Exception:
            pass
    return StandardsConfig()


def _ensure_layer(doc, name: str, color: int = 7) -> None:
    if name not in doc.layers:
        doc.layers.new(name=name)
        try:
            doc.layers.get(name).color = color
        except Exception:
            pass


def _symbol_for(tag: str, cfg: StandardsConfig) -> Optional[str]:
    """Return a symbol DXF path (string) for a given tag, if configured."""
    mapping = (getattr(cfg, "symbols", None) or {})
    t = (tag or "").lower()
    if t.startswith("rec") or t.startswith("r-"):
        return mapping.get("receptacle")
    if t.startswith("l") or "lum" in t:
        return mapping.get("luminaire")
    if "panel" in t or t.startswith("pnl") or t.startswith("panel"):
        return mapping.get("panel")
    if t.startswith("s") and ("switch" in t or len(t) <= 3):
        return mapping.get("switch")
    return None


# ---------- main generator ----------
def generate_one_line_dxf(req: OneLineRequest, out_path: Path) -> None:
    doc = ezdxf.new(dxfversion="R2010")
    msp = doc.modelspace()

    # -- standards --
    cfg = _load_standards()
    lyr_ann = cfg.layers.get("annotations", "E-ANNO-TEXT"); _ensure_layer(doc, lyr_ann)
    lyr_panels = cfg.layers.get("panels", "E-POWR-PNLS"); _ensure_layer(doc, lyr_panels)
    lyr_power_devices = cfg.layers.get("power_devices", "E-POWR-DEV"); _ensure_layer(doc, lyr_power_devices)

    # v5 titleblock (optional)
    if cfg.titleblock:
        tb_path = (_Path(__file__).resolve().parents[1] / "standards" / cfg.titleblock) if not _Path(cfg.titleblock).is_absolute() else _Path(cfg.titleblock)
        if tb_path.exists():
            try:
                blk_name = tb_path.stem
                import_dxf_as_block(doc, tb_path, blk_name)
                insert_block(msp, blk_name, insert=(0, 0), layer=lyr_ann)
            except Exception:
                # non-fatal if the titleblock fails to import/insert
                pass

    # title/header
    msp.add_text(
        f"{req.project} - One-Line Diagram",
        dxfattribs={"height": 0.3, "layer": lyr_ann}
    ).set_pos((0, 7), align=TextEntityAlignment.LEFT)
    msp.add_text(
        f"Service: {req.service_voltage} {req.service_amperes}A",
        dxfattribs={"height": 0.2, "layer": lyr_ann}
    ).set_pos((0, 6.5))
    msp.add_circle((0, 6), radius=0.1, dxfattribs={"layer": lyr_ann})
    msp.add_text("UTILITY", dxfattribs={"height": 0.15, "layer": lyr_ann}).set_pos((0.2, 6))

    # panels and loads
    y = 5.5
    for p in req.panels:
        msp.add_line((0, y), (2, y), dxfattribs={"layer": lyr_panels})
        msp.add_text(
            f"{p.name} {p.voltage} {p.bus_amperes}A",
            dxfattribs={"height": 0.18, "layer": lyr_ann}
        ).set_pos((2.1, y - 0.05))

        by = y - 0.3
        panel_loads = [L for L in req.loads if L.panel == p.name]
        for ld in panel_loads:
            msp.add_line((2, by), (3, by), dxfattribs={"layer": lyr_power_devices})

            # try symbol; fallback to a circle
            sym_path_str = _symbol_for(ld.name, cfg)
            placed = False
            if sym_path_str:
                sp = _Path(sym_path_str)
                try:
                    import_dxf_as_block(doc, sp, sp.stem)
                    placed = insert_block(msp, sp.stem, insert=(3.2, by), layer=lyr_power_devices)
                except Exception:
                    placed = False
            if not placed:
                msp.add_circle((3.2, by), radius=0.04, dxfattribs={"layer": lyr_power_devices})

            msp.add_text(
                f"{ld.name} {ld.kva} kVA",
                dxfattribs={"height": 0.14, "layer": lyr_ann}
            ).set_pos((3.4, by - 0.05))

            by -= 0.3

        y -= max(0.6, 0.3 * max(1, len(panel_loads)))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(out_path)