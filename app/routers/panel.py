from __future__ import annotations
from typing import Optional, Dict, Union
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ValidationError
from pathlib import Path
import tempfile, shutil, zipfile, os

# --- Internal project imports ---
from app.schemas.panel_ir import PanelScheduleIR                  # IR schema for panel schedule
from app.io.panel_excel import write_excel_from_ir                # IR → Excel (.xlsx), preserves template formatting
from app.export.pdf import export_pdf_from_ir                     # IR → PDF
from app.routers.preflight import _kva_formulas_per_phase         # Server-side fallback KVA formulas

# --- FastAPI Router Setup ---
router = APIRouter(prefix="/panel", tags=["panel"])

# --- Key paths ---
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
OUT.mkdir(parents=True, exist_ok=True)
TEMPLATE_XLSX = ROOT / "templates" / "panelboard_template.xlsx"


# -------------------------------------------------------------------
# MODELS
# -------------------------------------------------------------------
class ExportPayload(BaseModel):
    """
    Preferred request body for /panel/export/zip:
      {
        "ir": { ...PanelScheduleIR... },
        "_kva_formulas": { "G57": "=G56*277/1000", ... },   # optional (from GPT)
        "_inferred_system": "3PH WYE, GROUNDED"             # optional (from GPT)
      }

    Aliases let us use underscore keys in JSON while accessing them as
    .kva_formulas / .inferred_system in Python.
    """
    ir: PanelScheduleIR
    kva_formulas: Optional[Dict[str, str]] = Field(default=None, alias="_kva_formulas")
    inferred_system: Optional[str] = Field(default=None, alias="_inferred_system")

    model_config = {
        "populate_by_name": True,      # allow using field names or aliases
        "protected_namespaces": (),    # permit alias keys that start with '_' in JSON
    }


# -------------------------------------------------------------------
# ENDPOINTS
# -------------------------------------------------------------------

@router.post("/export/zip")
def export_zip(
    payload: Union[ExportPayload, PanelScheduleIR],
    background_tasks: BackgroundTasks,
    confirm: bool = Query(False),
):
    """
    Builds an Excel + PDF panel schedule and returns a ZIP.
    - Accepts EITHER:
        1) ExportPayload (preferred): { ir, _kva_formulas?, _inferred_system? }
        2) Raw PanelScheduleIR (legacy clients)
    - Uses GPT-provided formulas when present; otherwise falls back to server logic.
    - `confirm` is reserved (e.g., to enforce preflight confirmation on the server).
    """
    # ---- 1) Extract & validate IR; capture GPT extras if present ----
    if isinstance(payload, PanelScheduleIR):
        ir = payload
        gpt_formulas = None
        # inferred_system unused server-side for now, but kept for future logging/telemetry
    else:
        ir = payload.ir
        gpt_formulas = payload.kva_formulas
        # payload.inferred_system is available if you want to log/emit it

    try:
        ir = PanelScheduleIR.model_validate(ir)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.errors())

    # ---- 2) Guard: ensure template exists ----
    if not TEMPLATE_XLSX.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Master template not found at {TEMPLATE_XLSX}. "
                   "Place 'panelboard_template.xlsx' under /templates."
        )

    # ---- 3) Choose formulas (prefer GPT; otherwise compute) ----
    formulas = gpt_formulas or _kva_formulas_per_phase(ir)

    # (Optional) enforce confirmation on server side in the future:
    # if not confirm:
    #     raise HTTPException(status_code=409, detail="Build not confirmed by user.")

    # ---- 4) Build in a temporary workdir ----
    workdir = Path(tempfile.mkdtemp())
    try:
        placeholder_xlsx = workdir / "panel_schedule.xlsx"

        # Excel writer returns the final saved path inside OUT with your filename convention
        excel_real_path = write_excel_from_ir(
            ir=ir,
            out_path=str(placeholder_xlsx),
            template_xlsx=str(TEMPLATE_XLSX),
            formulas=formulas,
        )

        # Matching PDF next to the Excel
        pdf_path = excel_real_path.with_suffix(".pdf")
        export_pdf_from_ir(ir=ir, out_pdf=str(pdf_path))

        # Zip them together using the Excel base name
        zip_name = excel_real_path.with_suffix("").name + ".zip"
        dest_zip = OUT / zip_name
        with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(excel_real_path, excel_real_path.name)
            zf.write(pdf_path, pdf_path.name)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    # ---- 5) Cleanup the ZIP after response is sent ----
    def _cleanup(path: str):
        try:
            os.remove(path)
        except OSError:
            pass
    background_tasks.add_task(_cleanup, str(dest_zip))

    # ---- 6) Return the ZIP ----
    return FileResponse(
        path=str(dest_zip),
        filename=dest_zip.name,       # e.g., panel_LP-1_208-120V.zip
        media_type="application/zip",
        background=background_tasks,
    )