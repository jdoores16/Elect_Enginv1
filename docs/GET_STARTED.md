
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



## (Optional) Activate Your Project Standards
1. Prepare a `standards.json` like:
```json
{
  "layers": {
    "power_devices": "E-POWR-DEV",
    "lighting": "E-LITE-FIXT",
    "panels": "E-POWR-PNLS",
    "annotations": "E-ANNO-TEXT",
    "rooms": "E-ANNO-ROOM"
  },
  "text_style": "ROMANS",
  "dim_style": "ARCH",
  "titleblock": "Titleblock-A1.dxf"
}
```
2. In the web UI, upload this file (and optional titleblock DXF/DWG) under **Upload Project Standards**.
3. The CAD generators will now use your layer names and annotate on your text layer.


### Symbols (optional)
Add DXF files under `/symbols` (e.g., `receptacle.dxf`, `panelboard.dxf`, `2x2_luminaire.dxf`). Then reference them in `standards.json`:

```json
{
  "symbols": {
    "receptacle": "symbols/receptacle.dxf",
    "panel": "symbols/panelboard.dxf",
    "luminaire": "symbols/2x2_luminaire.dxf",
    "switch": "symbols/switch_single.dxf"
  }
}
```
The generators will insert these blocks instead of primitive circles/squares when tags match.


## (Optional) Enable ChatGPT (LLM Planning)
1. Add `OPENAI_API_KEY` (Replit Secrets or a local `.env`).
2. The app will summarize your command and build a JSON plan for the CAD generators.
3. If no key is present, a safe fallback plan is used so the app still runs.
