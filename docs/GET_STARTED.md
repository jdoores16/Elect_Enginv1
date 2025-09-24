
# Get Started (Beginner Friendly)

> Goal: run the starter, drop your files, speak a command, and download a DXF—no prior coding required.

## 1) Create a Repl
1. Go to https://replit.com → New Repl → **Python**.
2. Drag the project ZIP into the file pane (or GitHub import) and extract it.

## 2) Run
- Click **Run**.
- When the web preview opens, you should see the AI PE Assistant UI.

## 3) Add Resources
- Drag floor plans (DXF/DWG/PDF), cut sheets, photos, or notes into the **Resource Bucket**.

## 4) Ask for Output
- Hold **🎙️** and say one of these:
  - “Create a one-line at 480Y/277V, 2000A service.”
  - “Generate a power plan for the lobby and electrical room.”
  - “Make a lighting plan with two luminaires in the conference room.”
  - “Export a Revit package for this project.”
- Or type a command in the textbox and click **Run Command**.

## 5) Download
- Check **Outputs** → click a file to download (DXF/JSON).

---

### Optional: Enable an AI Model
Right now the routing is keyword-based. To use an AI model later:
1. Add your API key to Replit **Secrets** (lock icon).
2. Edit `app/ai/llm.py` to call your provider and return **structured JSON** the CAD modules can draw.
3. Keep CAD generation deterministic and review outputs before sealing.

