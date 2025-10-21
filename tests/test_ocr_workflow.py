"""
Integration tests for the enhanced OCR workflow: analyze → edit → submit.
Verifies the complete IR-centric pipeline works end-to-end.
"""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import json

from app.main import app

client = TestClient(app)

BUCKET = Path("bucket")
OUT = Path("out")


def test_ocr_workflow_analyze_endpoint():
    """Test that /api/ocr/analyze endpoint works"""
    # This would need actual image files to work fully
    # For now, just test the endpoint exists and returns proper error
    response = client.post("/api/ocr/analyze", json={
        "session": "test_session",
        "files": []
    })
    
    # Should return 400 for no files
    assert response.status_code == 400
    assert "No image files" in response.json()["detail"]


def test_ocr_workflow_latest_endpoint():
    """Test that /api/ocr/latest endpoint works"""
    response = client.get("/api/ocr/latest?session=nonexistent")
    
    # Should return 404 for non-existent session
    assert response.status_code == 404
    assert "No OCR data found" in response.json()["detail"]


def test_ocr_workflow_submit_edits_structure():
    """Test that submit_edits accepts properly structured data"""
    # Mock edited data structure
    edited_data = {
        "session": "test",
        "panel_specs": {
            "panel_name": "TEST-PANEL",
            "voltage": "480Y/277V",
            "phase": "3PH",
            "wire": "4W+G",
            "main_bus_amps": "800",
            "main_circuit_breaker": "MLO",
            "mounting": "SURFACE",
            "feed": "UPSTREAM",
            "feed_thru_lugs": "NO",
            "location": "ELECTRICAL ROOM",
            "fed_from": "MSB-1",
            "ul_listed_equipment_short_circuit_rating": "22kA",
            "maximum_available_short_circuit_current": "18kA",
            "phase_conductor": "#1/0 CU",
            "neutral_conductor": "#1/0 CU",
            "ground_conductor": "#6 CU"
        },
        "circuits": [
            {
                "number": "1",
                "description": "LIGHTING",
                "load": "5.0",
                "breaker_amps": "20",
                "breaker_poles": "1"
            },
            {
                "number": "2",
                "description": "RECEPTACLES",
                "load": "3.5",
                "breaker_amps": "20",
                "breaker_poles": "1"
            }
        ]
    }
    
    response = client.post("/api/ocr/submit_edits", json=edited_data)
    
    # Should succeed and return file info
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "file" in data
    assert data["file"].endswith(".xlsx")


def test_manual_edits_to_ir_conversion():
    """Test that manual edits can be converted to IR"""
    from app.skills.ocr_to_ir import manual_edits_to_ir
    
    edited_data = {
        "panel_specs": {
            "panel_name": "PP-1",
            "voltage": "208/120V",
            "phase": "1PH",
            "wire": "3W+G",
            "main_bus_amps": "225",
            "main_circuit_breaker": "200A"
        },
        "circuits": [
            {
                "number": "1",
                "description": "LIGHTS",
                "load": "10",
                "breaker_amps": "20",
                "breaker_poles": "1"
            }
        ]
    }
    
    ir = manual_edits_to_ir(edited_data)
    
    assert ir.header.panel_name == "PP-1"
    assert len(ir.circuits) == 1
    assert ir.circuits[0].description == "LIGHTS"
    assert ir.circuits[0].breaker_amps == 20.0


def test_confidence_scoring_structure():
    """Test that confidence scoring produces correct structure"""
    from app.skills.ocr_enhanced import FieldExtraction, ConfidenceLevel
    
    field = FieldExtraction(
        field_name="voltage",
        value="480Y/277V",
        confidence=0.95,
        confidence_level=ConfidenceLevel.HIGH,
        source_line="VOLTAGE: 480Y/277V"
    )
    
    result = field.to_dict()
    
    assert result["field_name"] == "voltage"
    assert result["value"] == "480Y/277V"
    assert result["confidence"] == 0.95
    assert result["confidence_level"] == "high"
    assert result["needs_review"] == False


def test_fuzzy_matching():
    """Test fuzzy field matching works"""
    from app.skills.ocr_enhanced import fuzzy_match_score
    
    # Perfect match
    assert fuzzy_match_score("VOLTAGE", "VOLTAGE") == 1.0
    
    # Similar
    score = fuzzy_match_score("VOLTAG", "VOLTAGE")
    assert score > 0.8
    
    # Different
    score = fuzzy_match_score("PHASE", "VOLTAGE")
    assert score < 0.5
