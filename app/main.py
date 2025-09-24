from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import shutil, uuid, os, json
from typing import List

from app.schemas.models import OneLineRequest, PlanRequest
from app.cad.one_line import generate_one_line_dxf
from app.cad.power_plan import generate_power_plan_dxf
from app.cad.lighting_plan import generate_lighting_plan_dxf

ROOT = Path(__file__).resolve().parent.parent
BUCKET = ROOT / "bucket"
OUT = ROOT / "out"
STATIC = ROOT / "static"

app = FastAPI(title="AI PE Assistant (Drag & Drop + Voice)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static frontend
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

@app.get("/", response_class=HTMLResponse)
def home():
    index = (STATIC / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(index)

@app.get("/health")
def health():
    return {"status": "ok"}

# ---- Bucket (drag & drop) ----
@app.post("/upload")
async def upload(files: List[UploadFile] = File(...)):
    BUCKET.mkdir(parents=True, exist_ok=True)
    saved = []
    for f in files:
        dest = BUCKET / f.filename
        with dest.open("wb") as out:
            shutil.copyfileobj(f.file, out)
        saved.append(f.filename)
    return {"saved": saved}

@app.get("/bucket/list")
def bucket_list():
    BUCKET.mkdir(exist_ok=True)
    files = sorted([p.name for p in BUCKET.iterdir() if p.is_file()])
    return {"files": files}

@app.get("/bucket/file/{name}")
def bucket_file(name: str):
    path = BUCKET / name
    if not path.exists():
        raise HTTPException(404, "Not found")
    return FileResponse(str(path))

@app.post("/bucket/clear")
def bucket_clear():
    if BUCKET.exists():
        for p in BUCKET.iterdir():
            if p.is_file():
                p.unlink()
    return {"status": "cleared"}

# ---- Outputs list (for UI) ----
@app.get("/outputs/list")
def outputs_list():
    OUT.mkdir(exist_ok=True)
    files = sorted([p.name for p in OUT.iterdir() if p.is_file()])
    return {"files": files}

@app.get("/out/{name}")
def out_file(name: str):
    path = OUT / name
    if not path.exists():
        raise HTTPException(404, "Not found")
    return FileResponse(str(path))

# ---- CAD endpoints (unchanged programmatic access) ----
@app.post("/cad/one_line")
def cad_one_line(req: OneLineRequest):
    OUT.mkdir(parents=True, exist_ok=True)
    out_path = OUT / f"one_line_{uuid.uuid4().hex}.dxf"
    generate_one_line_dxf(req, out_path)
    return {"file": out_path.name}

@app.post("/cad/power_plan")
def cad_power_plan(req: PlanRequest):
    OUT.mkdir(parents=True, exist_ok=True)
    out_path = OUT / f"power_plan_{uuid.uuid4().hex}.dxf"
    generate_power_plan_dxf(req, out_path)
    return {"file": out_path.name}

@app.post("/cad/lighting_plan")
def cad_lighting_plan(req: PlanRequest):
    OUT.mkdir(parents=True, exist_ok=True)
    out_path = OUT / f"lighting_plan_{uuid.uuid4().hex}.dxf"
    generate_lighting_plan_dxf(req, out_path)
    return {"file": out_path.name}

# ---- Voice/typed command dispatcher ----
@app.post("/commands/run")
def run_command(payload: dict):
    text = (payload.get("text") or "").lower()
    if not text:
        raise HTTPException(400, "No command text provided.")
    OUT.mkdir(parents=True, exist_ok=True)

    # Very simple intent routing (replace with LLM later)
    if "one-line" in text or "one line" in text:
        # Minimal demo input
        req = {
            "project": "Voice-Created Project",
            "service_voltage": "480Y/277V",
            "service_amperes": 2000,
            "panels": [
                {"name": "MDS", "voltage": "480Y/277V", "bus_amperes": 1200},
                {"name": "L1", "voltage": "208Y/120V", "bus_amperes": 400}
            ],
            "loads": [
                {"name": "CHWP-1", "kva": 50.0, "panel": "MDS"},
                {"name": "RTU-2", "kva": 35.0, "panel": "MDS"},
                {"name": "REC-GEN", "kva": 10.0, "panel": "L1"}
            ]
        }
        name = f"one_line_{uuid.uuid4().hex}.dxf"
        generate_one_line_dxf(OneLineRequest(**req), OUT / name)
        return {"message": "One-line DXF generated.", "file": name}

    if "power plan" in text:
        req = {
            "project": "Voice-Created Power Plan",
            "rooms": [
                {"name": "Lobby", "x": 0, "y": 0, "w": 6, "h": 4},
                {"name": "Elec", "x": 0, "y": 4.2, "w": 3, "h": 2}
            ],
            "devices": [
                {"tag": "REC-1", "x": 1, "y": 1},
                {"tag": "REC-2", "x": 2, "y": 1.5},
                {"tag": "PANEL-L1", "x": 0.5, "y": 4.8}
            ]
        }
        name = f"power_plan_{uuid.uuid4().hex}.dxf"
        generate_power_plan_dxf(PlanRequest(**req), OUT / name)
        return {"message": "Power plan DXF generated.", "file": name}

    if "lighting plan" in text:
        req = {
            "project": "Voice-Created Lighting Plan",
            "rooms": [
                {"name": "Lobby", "x": 0, "y": 0, "w": 6, "h": 4},
                {"name": "Conference", "x": 6.3, "y": 0, "w": 4, "h": 4}
            ],
            "devices": [
                {"tag": "L1", "x": 1.5, "y": 2.0},
                {"tag": "L2", "x": 4.5, "y": 2.0},
                {"tag": "S1", "x": 0.2, "y": 0.2}
            ]
        }
        name = f"lighting_plan_{uuid.uuid4().hex}.dxf"
        generate_lighting_plan_dxf(PlanRequest(**req), OUT / name)
        return {"message": "Lighting plan DXF generated.", "file": name}

    if "revit" in text or "export package" in text or "dynamo" in text:
        # Produce a JSON "task package" to import via Dynamo/pyRevit locally.
        pkg = {
            "package": "revit_task",
            "version": 1,
            "notes": "Import with your Dynamo/pyRevit script to place families and build sheets.",
            "resources": [f.name for f in BUCKET.iterdir() if f.is_file()] if BUCKET.exists() else [],
            "intent": "place families, create sheets",
            "example": {
                "levels": [{"name": "Level 1", "elevation_ft": 0.0}],
                "rooms": [{"name": "Lobby", "bbox": [0,0,6,4]}],
                "devices": [{"family": "Device-Receptacle", "room": "Lobby", "x": 1.0, "y": 1.0}]
            }
        }
        name = f"revit_task_{uuid.uuid4().hex}.json"
        (OUT / name).write_text(json.dumps(pkg, indent=2))
        return {"message": "Revit task JSON generated.", "file": name}

    return {"message": "Command understood but no generator matched. Try: one-line, power plan, lighting plan, revit package."}
