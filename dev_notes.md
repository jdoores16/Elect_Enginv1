# 🧠 AI DESIGN ENGINEER — Dev Notes (Context Anchor)
**Date:** Oct 20 2025  
**Engineer:** Josh (PE, Electrical)  
**Persona:** Josh — Licensed Electrical Engineer (PE), Hydro Power Systems Specialist, AI systems developer, and business owner  
**Experience Lens:** Programming (Python/FastAPI), electrical design automation (AutoCAD/Revit), and entrepreneurial scaling (AI consultant).  
**Repo:** [jdoores16/Elect_Enginv1](https://github.com/jdoores16/Elect_Enginv1)  
**Active branch:** `v9` → prepping `v10`  
**Working directory:** `C:\Users\jrdoo\Projects\AI DESIGN ENGINEER\AI_DESIGN_ENGINEER_GIT`  
**Next version source:** `C:\Users\jrdoo\Projects\AI DESIGN ENGINEER\ENGINEER 10`  
**Environment:** Windows 11 | Python 3.11 | FastAPI | OpenAI SDK | Replit linked  
**IDE / Tools:** Visual Studio Code + PowerShell + Replit  

---

## 🧩 Project Summary
AI Design Engineer is a FastAPI-based electrical design assistant capable of:
- Generating **panel schedules**, **one-line diagrams**, and **lighting/power plans**  
- Interacting through **voice/text commands**  
- Converting OCR panelboard photos into structured Excel/PDF deliverables  
- Integrating OpenAI LLM for natural-language plan generation (`app/ai/llm.py`)  
- Producing outputs via `/out` and `/bucket` FastAPI endpoints  

Josh’s current focus is on **stabilizing branch/version management** and ensuring version 10 becomes the new development baseline.

Josh's equal focus is on **higher accuracy and quantity of "photo parameters"** obtained from uploading photos to the bucket


---

## 🧱 Current Repository Structure
- **Local versions:** `ENGINEER V5` → `ENGINEER V9` under `C:\Users\jrdoo\Projects\AI DESIGN ENGINEER\`
- **Central Git working repo:** `AI_DESIGN_ENGINEER_GIT`
- **GitHub branches:** `v5 … v9` + `main`
- **Tags:** `v5.0 … v9.0`
- **Automation:** `import_versions_to_branches.ps1` successfully migrated all versions → branches  
- **Git identity:** configured (`jdoores16`, `jrdoores@gmail.com`)

---

## ⚙️ Latest Technical State
### ✅ Functional
- `run_server.ps1` sets up and launches FastAPI with venv + dependencies from `requirements.txt`.
- `app/ai/llm.py` rebuilt for schema-based OpenAI calls and safe fallbacks when API key missing.
- `main.py` endpoints (`/panel`, `/commands/run`, `/bucket`, `/outputs`) all operational.
- Local server tested successfully on `127.0.0.1:8000`.

### ⚠️ Known Issues / Notes
- LF → CRLF warnings during Git pushes (safe; Windows line endings).  
- OpenAI key must exist in `.env` (`OPENAI_API_KEY`, `OPENAI_MODEL` etc).  
- When no key present, LLM gracefully falls back to keyword parser.  
- Future script (`import_single_version.ps1`) will simplify adding new versions like `v10`.

---

## 🚀 Current Goals
1. Create and validate **ENGINEER 10 → v10** as next branch baseline.  
2. Implement **single-version import script** with clear inline comments.  
3. Keep a clean version log: `dev_notes.md` updated per session.  
4. Begin **intent-driven command flow test** (voice → `panel_schedule`).

---

## 🧭 Replit & GitHub Workflow
1. Develop in Replit (`Elect_Enginv1` repo connected).  
2. `git add . && git commit -m "[v10] <change summary>" && git push origin v10`  
3. Update this file’s “Recent Updates” section.  
4. Paste its summary at top of new ChatGPT sessions to rehydrate context.

---

## 🧾 Recent Updates
- Moved repo root → `C:\Users\jrdoo\Projects\AI DESIGN ENGINEER\`  
- Successfully imported v5–v9 branches + tags to GitHub.  
- Verified branch sync and tag recreation via PowerShell.  
- Confirmed main → v9 alignment (then forced to v6 during test).  
- Planning transition to v10 as active development branch.  

---

## 🪄 ChatGPT Handoff Summary (for context reload)
> Current version: **v9 (preparing v10)**  
> Repo: **https://github.com/jdoores16/Elect_Enginv1.git**  
> Working folder: **C:\Users\jrdoo\Projects\AI DESIGN ENGINEER\AI_DESIGN_ENGINEER_GIT**  
> Goal: **Create ENGINEER 10 branch (v10)** and continue FastAPI + LLM development.  
> Last known status: Git branches/tags validated; next step is scripting and pushing v10 import.

---

## 🧰 Next Steps (Checklist)
- [ ] Finalize `import_single_version.ps1` with comments & defaults  
- [ ] Import `ENGINEER 10` → `v10`  
- [ ] Tag `v10.0` and move main → v10  
- [ ] Test server startup from v10 branch  
- [ ] Commit this `dev_notes.md` to repo root 
- [ ] Continue to refine panelboard schedule creation
- [ ] Obtain better results from the Tyeserract software, ie high accuracy of parameter values from photos

