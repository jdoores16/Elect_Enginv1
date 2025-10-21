# app/ai/gpt_preflight.py
from __future__ import annotations
import os, textwrap
from typing import Dict, Any
from openai import OpenAI
from app.schemas.panel_ir import PanelScheduleIR
from app.ai.checklist import build_checklist, summarize_for_gpt

_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

def run_gpt_preflight(ir: PanelScheduleIR) -> Dict[str, Any]:
    """
    Sends a compact, structured summary + checklist to OpenAI and
    asks for a JSON result with Yes/No + notes per item and a final ok_to_build.
    """
    checklist = build_checklist(ir)
    context = summarize_for_gpt(ir)

    system = "You are a meticulous electrical design QA assistant. Be concise, factual, and conservative."
    user = textwrap.dedent(f"""
      Review the panel schedule data below against the CHECKLIST. Answer with strict JSON.

      ### DATA
      {context}

      ### CHECKLIST
      - {chr(10)+'- '.join(checklist)}

      ### OUTPUT FORMAT (strict JSON):
      {{
        "items": [
          {{"check": "<text of item 1>", "pass": true|false, "notes": "<short note>"}},
          ...
        ],
        "warnings": ["<short warning strings>"],
        "ok_to_build": true|false
      }}

      Rules:
      - If MAIN CIRCUIT BREAKER is larger than MAIN BUS AMPS (and not MLO), add a warning string exactly:
        "WARNING: MAIN CIRCUIT BREAKER IS LARGER THAN MAIN BUS AMPS"
      - Keep notes short. If uncertain, mark pass=false and explain why.
      - ok_to_build is true only if no critical items fail (style-only issues can still pass).
    """)

    client = OpenAI()
    resp = client.chat.completions.create(
        model=_MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
    )

    content = resp.choices[0].message.content
    # It’s already JSON due to response_format; keep as string and let FastAPI return it,
    # or parse here if you want to enforce shape.
    import json
    try:
        data = json.loads(content)
    except Exception:
        data = {"items": [], "warnings": ["LLM returned non-JSON"], "ok_to_build": False, "__raw__": content}
    # Guardrail: always present arrays/fields
    data.setdefault("items", [])
    data.setdefault("warnings", [])
    data.setdefault("ok_to_build", False)
    return data