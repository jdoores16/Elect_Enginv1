# AI Design Engineer V7

AI-powered assistant for generating **electrical power system construction drawings and documents** from text or voice commands.  
It produces **DXF, PDF, CSV, DOCX, and ZIP packages** and includes a web-based UI with speech, visuals, and drag-and-drop.

---

## ✨ Features
- **Chat-style interface** with text input and **voice-to-text**.
- AI replies with **speech** (deep, calming voice) and **animated wave visualization** in the background.
- **Drag-and-drop** reference file upload.
- **Session isolation** for multiple projects.
- **CAD Generators**:
  - One-line diagrams
  - Power plans
  - Lighting plans
  - Panel schedules → CSV/Excel
- **PDF Export** with border + title footer metadata.
- **Build workflow**: outputs DXF, PDF, CSV, and a **summary Word DOCX** describing scope, ethics, PE review notes, and NEC references, all zipped.
- **OCR Skill**: Convert panelboard photos into an **Excel schedule** using Tesseract OCR.

---

## 🗂️ Repo Contents
```
AI DESIGN ENGINEER V7/.env
AI DESIGN ENGINEER V7/.env.txt
AI DESIGN ENGINEER V7/.replit
AI DESIGN ENGINEER V7/prompt_for_v3_starter.txt
AI DESIGN ENGINEER V7/README.md
AI DESIGN ENGINEER V7/replit.nix
AI DESIGN ENGINEER V7/requirements.txt
AI DESIGN ENGINEER V7/setup_env.bat
AI DESIGN ENGINEER V7/.git/COMMIT_EDITMSG
AI DESIGN ENGINEER V7/.git/config
AI DESIGN ENGINEER V7/.git/description
AI DESIGN ENGINEER V7/.git/FETCH_HEAD
AI DESIGN ENGINEER V7/.git/HEAD
AI DESIGN ENGINEER V7/.git/index
AI DESIGN ENGINEER V7/.git/ORIG_HEAD
AI DESIGN ENGINEER V7/.git/REBASE_HEAD
and more...

Key directories:
- `app/` → FastAPI app, AI logic, CAD generators, skills
- `app/cad/` → DXF generators for one-lines, power, lighting
- `app/skills/ocr_panel.py` → OCR → Excel panel schedule skill
- `app/export/` → DXF→PDF export logic with title annotation
- `static/` → Web UI (HTML, CSS, JS: chat interface, waveform, checklist, drag & drop)
- `bucket/` → Uploaded files (per session)
- `out/` → Generated outputs (DXF, PDF, CSV, DOCX, ZIP)
- `standards/` → Project CAD standards (layers, symbols, titleblocks)
- `requirements.txt` → Python dependencies

---

## 🚀 Setup (Windows)
1. Open PowerShell and navigate to this folder:
   ```powershell
   cd "AI DESIGN ENGINEER V7"
   ```
2. Run the setup script (creates `.venv` and installs deps):
   ```powershell
   .\setup_env.bat
   ```
3. Activate environment (if not auto-activated):
   ```powershell
   .venv\Scripts\Activate.ps1
   ```
4. Start the app:
   ```powershell
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
5. Open browser at [http://localhost:8000/static](http://localhost:8000/static).

---

## 🧪 Testing the System
- **Text input** → type design requests, AI replies with summaries + voice.
- **Voice input** → hold mic button and speak; words appear in textbox.
- **Wave animation** → background waves move with AI’s speech.
- **Drag & drop** → upload files into Bucket.
- **Build** → click Build to package DXF+PDF+CSV+DOCX+ZIP.
- **Checklist** → auto-updates based on current plan.

**OCR Panel Schedule Test:**
1. Drag panel photos into dropzone.
2. Call API:
   ```http
   POST /panel/ocr_to_excel
   {
     "files": null,
     "panel_name": "PB1",
     "session": "<auto>"
   }
   ```
3. Download `panel_schedule_*.xlsx` from Outputs.

---

## ⚖️ Ethics & Review
- Outputs are **drafts only** — require PE review and stamping.
- Summary DOCX highlights what requires PE oversight and cites NEC references.
