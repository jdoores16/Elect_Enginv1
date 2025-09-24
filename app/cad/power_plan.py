import ezdxf
from ezdxf.enums import TextEntityAlignment
from pathlib import Path
from app.schemas.models import PlanRequest

def generate_power_plan_dxf(req: PlanRequest, out_path: Path):
    doc = ezdxf.new(dxfversion="R2010")
    msp = doc.modelspace()

    msp.add_text(f"{req.project} - Power Plan", dxfattribs={"height":0.3}).set_pos((0,7), align=TextEntityAlignment.LEFT)

    for r in req.rooms:
        msp.add_lwpolyline([(r.x,r.y),(r.x+r.w,r.y),(r.x+r.w,r.y+r.h),(r.x,r.y+r.h),(r.x,r.y)], dxfattribs={"closed": True})
        msp.add_text(r.name, dxfattribs={"height":0.15}).set_pos((r.x+0.1, r.y+r.h-0.2))

    for d in req.devices:
        msp.add_circle((d.x,d.y), radius=0.06)
        msp.add_text(d.tag, dxfattribs={"height":0.12}).set_pos((d.x+0.1, d.y-0.05))

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(out_path)
