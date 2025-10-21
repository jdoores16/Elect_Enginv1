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
from app.ai.llm import plan_from_prompt, summarize_intent

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
def bucket_list(session: str | None = None):
    BUCKET.mkdir(exist_ok=True)
    files = sorted([p.name for p in BUCKET.iterdir() if p.is_file()])
    return {"files": _filter_session(files, session)}

@app.get("/bucket/file/{name}")
def bucket_file(name: str):
    path = BUCKET / name
    if not path.exists():
        raise HTTPException(404, "Not found")
    return FileResponse(str(path))

@app.post("/bucket/clear")
def bucket_clear(session: str | None = None):
    if BUCKET.exists():
        pref = _session_prefix(session)
        for p in list(BUCKET.iterdir()):
            if p.is_file() and (not pref or p.name.startswith(pref)):
                p.unlink()
    return {"status": "cleared"}

# ---- Outputs list (for UI) ----
@app.get("/outputs/list")
def outputs_list(session: str | None = None):
    OUT.mkdir(exist_ok=True)
    files = sorted([p.name for p in OUT.iterdir() if p.is_file()])
    return {"files": _filter_session(files, session)}

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
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "No command text provided.")
    OUT.mkdir(parents=True, exist_ok=True)

    summary = summarize_intent(text)
    plan = plan_from_prompt(text, str(BUCKET))
    task = (plan.get("task") or "").lower()

    if task == "one_line":
        req = OneLineRequest(**{
            "project": plan.get("project",""),
            "service_voltage": plan.get("service_voltage","480Y/277V"),
            "service_amperes": plan.get("service_amperes",2000),
            "panels": plan.get("panels",[]),
            "loads": plan.get("loads",[])
        })
        name = f"{_session_prefix(payload.get('session'))}one_line_{uuid.uuid4().hex}.dxf"
        generate_one_line_dxf(req, OUT / name)
        return {"summary": summary, "message": "One-line DXF generated.", "file": name, "plan": plan}

    if task == "power_plan":
        req = PlanRequest(**{
            "project": plan.get("project",""),
            "rooms": plan.get("rooms",[]),
            "devices": plan.get("devices",[])
        })
        name = f"{_session_prefix(payload.get('session'))}power_plan_{uuid.uuid4().hex}.dxf"
        generate_power_plan_dxf(req, OUT / name)
        return {"summary": summary, "message": "Power plan DXF generated.", "file": name, "plan": plan}

    if task == "lighting_plan":
        req = PlanRequest(**{
            "project": plan.get("project",""),
            "rooms": plan.get("rooms",[]),
            "devices": plan.get("devices",[])
        })
        name = f"lighting_plan_{uuid.uuid4().hex}.dxf"
        generate_lighting_plan_dxf(req, OUT / name)
        return {"summary": summary, "message": "Lighting plan DXF generated.", "file": name, "plan": plan}

    if task == "revit_package":
        name = f"{_session_prefix(payload.get('session'))}revit_task_{uuid.uuid4().hex}.json"
        (OUT / name).write_text(json.dumps(plan, indent=2))
        return {"summary": summary, "message": "Revit task JSON generated.", "file": name, "plan": plan}

    return {"summary": summary, "message": f"Task '{task}' not recognized. Try: one_line, power_plan, lighting_plan, revit_package.", "plan": plan}

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
        name = f"{_session_prefix(payload.get('session'))}power_plan_{uuid.uuid4().hex}.dxf"
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
        name = f"{_session_prefix(payload.get('session'))}revit_task_{uuid.uuid4().hex}.json"
        (OUT / name).write_text(json.dumps(pkg, indent=2))
        return {"message": "Revit task JSON generated.", "file": name}

    return {"message": "Command understood but no generator matched. Try: one-line, power plan, lighting plan, revit package."}


from app.schemas.standards import StandardsConfig

STANDARDS_DIR = ROOT / "standards"
ACTIVE_STANDARDS = STANDARDS_DIR / "active.json"

def load_standards() -> StandardsConfig:
    STANDARDS_DIR.mkdir(exist_ok=True)
    if ACTIVE_STANDARDS.exists():
        try:
            return StandardsConfig(**json.loads(ACTIVE_STANDARDS.read_text()))
        except Exception:
            pass
    cfg = StandardsConfig()
    ACTIVE_STANDARDS.write_text(json.dumps(cfg.model_dump(), indent=2))
    return cfg

@app.post("/standards/upload")
async def standards_upload(config: UploadFile = File(None), titleblock: UploadFile = File(None)):
    STANDARDS_DIR.mkdir(exist_ok=True)
    result = {}
    if config is not None:
        text = config.file.read().decode("utf-8", errors="ignore")
        try:
            cfg_json = json.loads(text)
        except Exception:
            # fallback: simple key:value parser
            cfg_json = {}
            for line in text.splitlines():
                if ":" in line and not line.strip().startswith("#"):
                    k,v = line.split(":",1)
                    cfg_json[k.strip()] = v.strip()
            if "layers" not in cfg_json:
                cfg_json = {"layers": {"annotations": "E-ANNO-TEXT"}}
        ACTIVE_STANDARDS.write_text(json.dumps(cfg_json, indent=2))
        result["config"] = "saved"
    if titleblock is not None:
        tb_name = titleblock.filename
        tb_path = STANDARDS_DIR / tb_name
        with tb_path.open("wb") as f:
            f.write(titleblock.file.read())
        cfg = load_standards()
        cfg.titleblock = tb_name
        ACTIVE_STANDARDS.write_text(json.dumps(cfg.model_dump(), indent=2))
        result["titleblock"] = tb_name
    if not result:
        raise HTTPException(400, "No files uploaded.")
    return result

@app.get("/standards/get")
def standards_get():
    cfg = load_standards()
    return cfg.model_dump()


from fastapi import Body
import csv, io

@app.post("/cad/panel_schedule_csv")
def cad_panel_schedule_csv(req: OneLineRequest = Body(...)):
    """Export a very simple panel schedule CSV from the OneLineRequest."""
    # Aggregate loads by panel
    by_panel = {}
    for ld in req.loads:
        by_panel.setdefault(ld.panel, []).append(ld)
    csv_buf = io.StringIO()
    writer = csv.writer(csv_buf)
    writer.writerow(["Panel", "Load Name", "kVA"])
    for pnl, loads in by_panel.items():
        for ld in loads:
            writer.writerow([pnl, ld.name, ld.kva])
    content = csv_buf.getvalue().encode("utf-8")
    out_path = OUT / f"{_session_prefix(None)}panel_schedule_{uuid.uuid4().hex}.csv"
    with open(out_path, "wb") as f:
        f.write(content)
    return {"file": out_path.name}



# ---- DXF → PDF export ----
from app.export.pdf_from_dxf import dxf_to_pdf

@app.get("/export/pdf")
def export_pdf(file: str, session: str | None = None):
    # convert an existing DXF in OUT directory to a PDF with same stem
    dxf_path = OUT / file
    if not dxf_path.exists() or not dxf_path.suffix.lower() in [".dxf"]:
        raise HTTPException(400, "Provide a DXF file name that exists in /outputs/list.")
    pdf_name = Path(file).with_suffix(".pdf").name
    pdf_path = OUT / pdf_name
    dxf_to_pdf(dxf_path, pdf_path)
    return {"message": "PDF generated.", "file": pdf_name}


# ---- Build ZIP with summary DOCX ----
from docx import Document
from datetime import datetime
import zipfile as _zipfile

def _write_summary_docx(plan: dict, out_dir: Path) -> Path:
    doc = Document()
    doc.add_heading('AI Design Engineer - Summary', level=1)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    doc.add_paragraph(f"Timestamp: {now}")
    doc.add_paragraph(" ")
    # Plan echo
    doc.add_heading('What was requested (my understanding)', level=2)
    doc.add_paragraph(json.dumps(plan, indent=2))

    # What was done
    doc.add_heading('What was done & why', level=2)
    doc.add_paragraph("Generated draft design artifacts based on your instructions and project standards. "
                      "Outputs are provided in the ZIP. Rationale: match scope to request, adhere to configured layers/symbols, "
                      "and provide deterministic CAD structure for downstream PE review.")

    # Ethics
    doc.add_heading('Ethical considerations', level=2)
    doc.add_paragraph("This draft was produced by an AI-assisted workflow. It should be reviewed by a licensed Professional Engineer "
                      "before use in construction. The intent is to improve efficiency while maintaining public safety and code compliance. "
                      "All generative steps are logged via inputs/plan to preserve auditability.")

    # PE review
    doc.add_heading('PE review checklist', level=2)
    doc.add_paragraph("- Confirm service size, feeder/breaker coordination, and fault current assumptions.\n"
                      "- Verify equipment ratings and selective coordination where required.\n"
                      "- Validate conductor sizes, voltage drop and grounding/bonding details.\n"
                      "- Confirm device locations against architectural constraints and egress.\n"
                      "- Stamp only after verifying that calculations, notes, and details meet local/state amendments.")

    # NEC references (generic, non-exhaustive)
    doc.add_heading('Relevant NEC sections (non-exhaustive)', level=2)
    doc.add_paragraph("Articles commonly implicated by power plans and one-lines may include: 90 (Introduction & Enforcement), "
                      "100 (Definitions), 110 (Requirements for Electrical Installations), 200 (Use and Identification of Grounded Conductors), "
                      "210 (Branch Circuits), 215 (Feeders), 220 (Branch-Circuit, Feeder, and Service Calculations), "
                      "225 (Outside Branch Circuits and Feeders), 230 (Services), 240 (Overcurrent Protection), "
                      "250 (Grounding and Bonding), 300 (Wiring Methods), 310 (Conductors), 408 (Switchboards, Switchgear, Panelboards), "
                      "450 (Transformers), 700/701/702 (Emergency/Legally Required/Optional Standby), 760 (Fire Alarm), 800+ (Communications) as applicable.")

    out_path = out_dir / f"summary_{uuid.uuid4().hex}.docx"
    doc.save(str(out_path))
    return out_path

@app.post("/export/build_zip")
def export_build_zip(payload: dict):
    """
    Finalizes a build:
      - Re-runs the selected task from 'payload' to ensure fresh outputs
      - Creates a summary DOCX capturing scope, ethics, PE checklist, and NEC references
      - Zips all generated artifacts for download
    Expected payload:
      {
        "intent": "one_line" | "power_plan" | "lighting_plan",
        "plan": {...},                   # structured JSON produced by plan_from_prompt (or customized)
        "outputs": ["dxf","pdf","csv"]   # desired formats
      }
    """
    plan = payload.get("plan") or {}
    intent = (payload.get("intent") or "").lower()
    outputs = payload.get("outputs") or ["dxf","pdf"]

    OUT.mkdir(parents=True, exist_ok=True)

    generated = []

    if intent == "one_line":
        req = OneLineRequest(**{
            "project": plan.get("project",""),
            "service_voltage": plan.get("service_voltage","480Y/277V"),
            "service_amperes": plan.get("service_amperes",2000),
            "panels": plan.get("panels",[]),
            "loads": plan.get("loads",[])
        })
        dxf_name = f"{_session_prefix(payload.get('session'))}one_line_{uuid.uuid4().hex}.dxf"
        dxf_path = OUT / dxf_name
        generate_one_line_dxf(req, dxf_path)
        generated.append(dxf_name)
        if "pdf" in outputs:
            from app.export.pdf_from_dxf import dxf_to_pdf
            pdf_name = dxf_name.replace(".dxf",".pdf")
            dxf_to_pdf(dxf_path, OUT / pdf_name)
            generated.append(pdf_name)

    elif intent == "power_plan":
        req = PlanRequest(**{
            "project": plan.get("project",""),
            "rooms": plan.get("rooms",[]),
            "devices": plan.get("devices",[])
        })
        dxf_name = f"{_session_prefix(payload.get('session'))}power_plan_{uuid.uuid4().hex}.dxf"
        dxf_path = OUT / dxf_name
        generate_power_plan_dxf(req, dxf_path)
        generated.append(dxf_name)
        if "pdf" in outputs:
            from app.export.pdf_from_dxf import dxf_to_pdf
            pdf_name = dxf_name.replace(".dxf",".pdf")
            dxf_to_pdf(dxf_path, OUT / pdf_name)
            generated.append(pdf_name)

    elif intent == "lighting_plan":
        req = PlanRequest(**{
            "project": plan.get("project",""),
            "rooms": plan.get("rooms",[]),
            "devices": plan.get("devices",[])
        })
        dxf_name = f"{_session_prefix(payload.get('session'))}lighting_plan_{uuid.uuid4().hex}.dxf"
        dxf_path = OUT / dxf_name
        generate_lighting_plan_dxf(req, dxf_path)
        generated.append(dxf_name)
        if "pdf" in outputs:
            from app.export.pdf_from_dxf import dxf_to_pdf
            pdf_name = dxf_name.replace(".dxf",".pdf")
            dxf_to_pdf(dxf_path, OUT / pdf_name)
            generated.append(pdf_name)

    # Optional CSV panel schedule if present in plan
    if "panel_schedule" in plan and isinstance(plan["panel_schedule"], dict):
        by_panel = plan["panel_schedule"]
        import csv, io
        csv_buf = io.StringIO()
        writer = csv.writer(csv_buf)
        writer.writerow(["Panel", "Load Name", "kVA"])
        for pnl, loads in by_panel.items():
            for ld in loads:
                writer.writerow([pnl, ld.get("name",""), ld.get("kva","")])
        csv_name = f"{_session_prefix(payload.get('session'))}panel_schedule_{uuid.uuid4().hex}.csv"
        (OUT / csv_name).write_text(csv_buf.getvalue(), encoding="utf-8")
        generated.append(csv_name)

    # Create summary DOCX
    summary_path = _write_summary_docx(plan, OUT)
    generated.append(summary_path.name)

    # Zip it all
    zip_name = f"{_session_prefix(payload.get('session'))}build_{uuid.uuid4().hex}.zip"
    zip_path = OUT / zip_name
    with _zipfile.ZipFile(zip_path, "w", _zipfile.ZIP_DEFLATED) as z:
        for name in generated:
            z.write(OUT / name, arcname=name)

    return {"message": "Build package ready.", "zip": zip_name, "artifacts": generated}


# ---- Session helpers ----
def _session_prefix(session: str|None) -> str:
    if not session:
        return ""
    # keep it filesystem-safe
    safe = "".join(ch for ch in session if ch.isalnum() or ch in ("-","_"))[:40]
    return f"{safe}__"

def _filter_session(files, session: str|None):
    pref = _session_prefix(session)
    if not pref:
        return files
    return [f for f in files if f.startswith(pref)]
