# AI Design Engineer

An AI-powered assistant that generates **electrical design drawings and documents** from natural-language or voice commands.  
It combines **FastAPI backend services**, **CAD generators (ezdxf)**, and a **chat-style web UI** with speech, visuals, and build packaging.

---

## ✨ Features

- **Chat Interface**
  - Text or **voice-to-text** input
  - AI replies are spoken back with a **deep, soothing voice**
  - Background **waveform visualization** synced to AI speech
  - AI **summarizes your intent** to confirm understanding

- **File Handling**
  - Drag-and-drop reference files
  - Session-scoped buckets (isolate multiple projects)

- **CAD & Documents**
  - **One-line diagrams** (`/cad/one_line`)
  - **Power plans** (`/cad/power_plan`)
  - **Lighting plans** (`/cad/lighting_plan`)
  - **Panel schedules** → CSV export
  - **DXF → PDF** rendering with **title block frame + footer metadata**
  - **Build packages** (`/export/build_zip`):
    - DXF, PDF, CSV outputs
    - **Summary Word document (.docx)**:
      - What was done & why
      - Ethical considerations
      - PE review checklist
      - Relevant NEC sections

- **Review Checklist**
  - Sidebar checklist auto-updates based on the plan
  - Includes reminders like load calc validation, grounding, OCP, etc.

---

## 🗂️ Repo Structure

app/
main.py # FastAPI app, endpoints, orchestration
ai/llm.py # Intent planner and summarizer
cad/ # DXF generators (one-line, power, lighting)
schemas/ # Pydantic models for requests & standards
utils/ # Helpers (blocks, QA/QC)
export/
pdf_from_dxf.py # DXF→PDF converter with title block overlay
bucket/ # Uploaded reference files (per session)
out/ # Generated outputs (DXF, PDF, CSV, ZIP, DOCX)
standards/ # Active project standards (layers, symbols, titleblock)
static/ # Web frontend (HTML, CSS, JS)

## 🚀 Getting Started

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
Run server

bash
Copy code
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
Open UI

Go to: http://localhost:8000/static

🖥️ Usage Flow

Describe your design
Type or hold the mic to say:

"Generate a one-line diagram for a 480Y/277V, 2000A service with panels L1 and L2."

AI confirms
The assistant replies in text and voice, summarizing what it heard.

Iterate
Drag in reference drawings/specs.
The AI may ask clarifying questions or propose suggestions.

Review checklist
Sidebar auto-updates with NEC/code checks and review reminders.

Build
When satisfied, click Build:

All artifacts (DXF, PDF, CSV, DOCX) are packaged into a ZIP.

📦 Outputs

one_line_xxx.dxf + .pdf

power_plan_xxx.dxf + .pdf

lighting_plan_xxx.dxf + .pdf

panel_schedule_xxx.csv

summary_xxx.docx — narrative, ethics, PE review, NEC

build_xxx.zip — packaged outputs

⚖️ Ethics & Review

Outputs are drafts — not final construction documents.

Must be reviewed and stamped by a licensed Professional Engineer.

Audit logs (plans, configs) help maintain transparency.

🔮 Roadmap

Smarter QA/QC (short-circuit, voltage drop)

Direct Revit API/Dynamo integration

Cloud TTS for higher-quality AI voice

Configurable project standards (NEC edition, layers, title blocks)