import ezdxf
from ezdxf.enums import TextEntityAlignment
from pathlib import Path
from app.schemas.models import OneLineRequest

def generate_one_line_dxf(req: OneLineRequest, out_path: Path):
    doc = ezdxf.new(dxfversion="R2010")
    msp = doc.modelspace()

    msp.add_text(f"{req.project} - One-Line Diagram", dxfattribs={"height": 0.3}).set_pos((0, 7), align=TextEntityAlignment.LEFT)
    msp.add_text(f"Service: {req.service_voltage} {req.service_amperes}A", dxfattribs={"height":0.2}).set_pos((0,6.5))
    msp.add_circle((0,6), radius=0.1)
    msp.add_text("UTILITY", dxfattribs={"height":0.15}).set_pos((0.2,6))

    y = 5.5
    for p in req.panels:
        msp.add_line((0, y), (2, y))
        msp.add_text(f"{p.name} {p.voltage} {p.bus_amperes}A", dxfattribs={"height":0.18}).set_pos((2.1, y-0.05))
        by = y - 0.3
        for ld in [L for L in req.loads if L.panel == p.name]:
            msp.add_line((2, by), (3, by))
            msp.add_circle((3.2, by), radius=0.04)
            msp.add_text(f"{ld.name} {ld.kva} kVA", dxfattribs={"height":0.14}).set_pos((3.4, by-0.05))
            by -= 0.3
        y -= max(0.6, 0.3*max(1, len([L for L in req.loads if L.panel == p.name])))

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(out_path)
