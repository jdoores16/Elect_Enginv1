
# Roadmap: From MVP to Client-Ready

## Phase A — MVP (today)
- ✅ Upload bucket + voice/typed commands
- ✅ Generate DXF: one-line, power, lighting
- ✅ Export Revit task JSON

**You do:** Add your symbol blocks, layers, title blocks, and notes.

## Phase B — Smarter Planning (Weeks 1–2)
- Wire `app/ai/llm.py` to a model to convert program/cut sheets into:
  - Device lists by room
  - Paneling + one-line topology
  - Spec boilerplates (editable)
- Output *JSON → DXF* deterministically.

## Phase C — Real Backgrounds (Weeks 2–4)
- Upload background DXF; place devices with snapping/offsets.
- Circuiting hints (tag circuits, panel-feed annotations).

## Phase D — QA/QC & Calcs (Weeks 4–8)
- Automated checks: ampacity, VD, SCCR sanity, clearances.
- Export panel schedules CSV; short-circuit/VD stubs → your desktop tools.

## Phase E — Revit Workflow (Weeks 6–10)
- Dynamo/pyRevit ingests JSON → place families, build sheets.
- Round-trip changes back to JSON for audit trail.

## Phase F — Specs (ongoing)
- Template specs in Markdown/Docx (LLM-drafted, human-edited).

> At every phase: keep human-in-the-loop review and code compliance verification.
