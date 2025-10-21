"""
OCR Router: Enhanced OCR endpoints with confidence scoring and manual editing.
"""

from fastapi import APIRouter, HTTPException, Body
from pathlib import Path
from typing import Dict, List, Optional
import logging
import json

from app.skills.ocr_to_ir import ocr_to_ir, manual_edits_to_ir
from app.schemas.panel_ir import PanelScheduleIR
from app.io.panel_excel import write_excel_from_ir

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ocr", tags=["ocr"])

# In-memory storage for OCR results (temporary - could use database)
_ocr_cache: Dict[str, Dict] = {}

TEMPLATE_XLSX = Path("templates/panelboard_template.xlsx")

def _get_task_dirs(session: str):
    """Get task-specific directories for a session."""
    from app.main import get_task_directories
    uploads_dir, outputs_dir = get_task_directories(session)
    if not uploads_dir or not outputs_dir:
        raise HTTPException(404, "No active task found. Please start a task first.")
    return uploads_dir, outputs_dir


@router.post("/analyze")
def analyze_ocr(payload: dict = Body(...)):
    """
    Analyze OCR results with confidence scoring.
    Returns extraction metadata without generating files.
    """
    session = payload.get("session")
    if not session:
        raise HTTPException(400, "Session ID required")
    
    files = payload.get("files")
    
    # Get task-specific uploads directory
    uploads_dir, _ = _get_task_dirs(session)
    
    # Choose files
    if not files:
        files = [p.name for p in uploads_dir.iterdir() 
                if p.is_file() and p.suffix.lower() in [".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"]]
    
    if not files:
        raise HTTPException(400, "No image files found for OCR analysis")
    
    # Process images
    image_paths = [uploads_dir / f for f in files]
    
    try:
        ir, extraction = ocr_to_ir(
            image_paths=image_paths,
            panel_name_override=payload.get("panel_name"),
            number_of_ckts=payload.get("number_of_ckts")
        )
        
        # Store in cache for later retrieval
        result = extraction.to_dict()
        result['ir'] = ir.model_dump()  # Store IR for later use
        _ocr_cache[session] = result
        
        return {
            "status": "analyzed",
            "needs_manual_review": extraction.needs_manual_review,
            "overall_confidence": extraction.overall_confidence,
            "gaps": extraction.gaps,
            "stats": result['stats'],
            "edit_url": f"/static/ocr_edit.html?session={session}" if extraction.needs_manual_review else None
        }
        
    except Exception as e:
        logger.error(f"OCR analysis failed: {e}", exc_info=True)
        raise HTTPException(500, f"OCR analysis failed: {str(e)}")


@router.get("/latest")
def get_latest_ocr(session: str = "default"):
    """
    Get the latest OCR extraction result for a session.
    Used by the manual edit interface.
    """
    if session not in _ocr_cache:
        raise HTTPException(404, "No OCR data found for this session")
    
    return _ocr_cache[session]


@router.post("/submit_edits")
def submit_edits(edited_data: dict = Body(...)):
    """
    Submit manually edited OCR data and generate Excel.
    """
    session = edited_data.get("session")
    if not session:
        raise HTTPException(400, "Session ID required")
    
    try:
        # Convert edited data to IR
        ir = manual_edits_to_ir(edited_data)
        
        # Ensure template exists
        if not TEMPLATE_XLSX.exists():
            raise HTTPException(500, f"Template not found: {TEMPLATE_XLSX}")
        
        # Get task-specific outputs directory
        _, outputs_dir = _get_task_dirs(session)
        placeholder_xlsx = outputs_dir / "panel_schedule.xlsx"
        
        excel_path = write_excel_from_ir(
            ir=ir,
            out_path=str(placeholder_xlsx),
            template_xlsx=str(TEMPLATE_XLSX),
            outputs_dir=outputs_dir
        )
        
        # Clear cache
        if session in _ocr_cache:
            del _ocr_cache[session]
        
        return {
            "status": "success",
            "file": excel_path.name,
            "message": "Excel file generated from edited OCR data"
        }
        
    except Exception as e:
        logger.error(f"Failed to generate Excel from edits: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to generate Excel: {str(e)}")


@router.post("/to_excel")
def ocr_to_excel(payload: dict = Body(...)):
    """
    Direct OCR to Excel conversion (bypasses manual edit).
    Use this when confidence is high or user wants to skip review.
    """
    session = payload.get("session")
    if not session:
        raise HTTPException(400, "Session ID required")
    
    files = payload.get("files")
    
    # Get task-specific directories
    uploads_dir, outputs_dir = _get_task_dirs(session)
    
    # Choose files
    if not files:
        files = [p.name for p in uploads_dir.iterdir() 
                if p.is_file() and p.suffix.lower() in [".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"]]
    
    if not files:
        raise HTTPException(400, "No image files found")
    
    # Process images
    image_paths = [uploads_dir / f for f in files]
    
    try:
        ir, extraction = ocr_to_ir(
            image_paths=image_paths,
            panel_name_override=payload.get("panel_name"),
            number_of_ckts=payload.get("number_of_ckts")
        )
        
        # Ensure template exists
        if not TEMPLATE_XLSX.exists():
            raise HTTPException(500, f"Template not found: {TEMPLATE_XLSX}")
        
        # Generate Excel in task outputs directory
        placeholder_xlsx = outputs_dir / "panel_schedule.xlsx"
        
        excel_path = write_excel_from_ir(
            ir=ir,
            out_path=str(placeholder_xlsx),
            template_xlsx=str(TEMPLATE_XLSX),
            outputs_dir=outputs_dir
        )
        
        return {
            "status": "success",
            "file": excel_path.name,
            "confidence": extraction.overall_confidence,
            "needs_review": extraction.needs_manual_review,
            "gaps": extraction.gaps,
            "message": "Excel file generated from OCR"
        }
        
    except Exception as e:
        logger.error(f"OCR to Excel failed: {e}", exc_info=True)
        raise HTTPException(500, f"OCR to Excel failed: {str(e)}")
