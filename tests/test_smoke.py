import os
from pathlib import Path
from fastapi.testclient import TestClient

# Import the FastAPI app
from app.main import app, OUT

client = TestClient(app)

def test_outputs_list():
    r = client.get("/outputs/list")
    assert r.status_code == 200
    assert "files" in r.json()

def test_generate_one_line_and_list_outputs(tmp_path):
    # Ask the commands router to generate a simple one-line
    payload = {
        "text": "Create a one line for a 480Y/277V, 2000A service with panels L1 and L2.",
        "session": "ci-session"
    }
    r = client.post("/commands/run", json=payload)
    assert r.status_code == 200
    j = r.json()
    # When the task matches, your backend returns summary/plan/file
    assert "message" in j or "summary" in j
    # Not all code paths return a file immediately; check outputs directory instead
    out_files = [p.name for p in OUT.iterdir() if p.is_file()]
    assert any(f.endswith(".dxf") for f in out_files), f"No DXF found in {OUT}"

def test_pdf_export_if_dxf_exists():
    # If a DXF exists, try rendering to PDF (headless Agg backend)
    out_files = [p.name for p in OUT.iterdir() if p.is_file() and p.suffix.lower() == ".dxf"]
    if not out_files:
        return  # Already covered by previous test; skip gracefully
    dxf = out_files[0]
    r = client.get(f"/export/pdf?file={dxf}")
    # Either we succeed (200) or, if something changed, surface a clear error
    assert r.status_code == 200, r.text
    pdf_name = Path(dxf).with_suffix(".pdf").name
    assert (OUT / pdf_name).exists()