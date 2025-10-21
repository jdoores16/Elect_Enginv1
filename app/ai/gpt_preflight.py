# app/ai/gpt_preflight.py
from __future__ import annotations
import os, textwrap
from typing import Dict, Any
from openai import OpenAI
from app.schemas.panel_ir import PanelScheduleIR
from app.ai.checklist import build_checklist, summarize_for_gpt

_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
_API_KEY = os.getenv("OPENAI_API_KEY")

def run_gpt_preflight(ir: PanelScheduleIR) -> Dict[str, Any]:
    """
    Sends electrical engineering data to OpenAI for technical review.
    Focus: System design, safety, code compliance, electrical calculations.
    NO formatting or aesthetic review.
    """
    checklist = build_checklist(ir)
    context = summarize_for_gpt(ir)

    system = textwrap.dedent("""
        You are a licensed Professional Electrical Engineer (PE) performing a technical design review.
        
        YOUR ROLE:
        - Analyze electrical system design, safety, and code compliance
        - Validate electrical calculations (KVA, phase balance, conductor sizing)
        - Identify potential electrical hazards or design issues
        - Provide engineering insights and recommendations
        
        DO NOT REVIEW:
        - Formatting, aesthetics, or visual layout
        - Template structure or cell positioning
        - Font sizes, colors, or styling
        - Document appearance
        
        BE:
        - Technical and precise with electrical terminology
        - Conservative in safety assessments
        - Factual with NEC code references when applicable
        - Insightful about system design implications
    """).strip()
    
    user = textwrap.dedent(f"""
      Perform a comprehensive ELECTRICAL ENGINEERING REVIEW of this panel schedule.
      Focus on technical correctness, safety, and code compliance.

      ### PANEL DATA
      {context}

      ### TECHNICAL REVIEW CHECKLIST
      - {chr(10)+'- '.join(checklist)}

      ### OUTPUT FORMAT (strict JSON):
      {{
        "items": [
          {{"check": "<checklist item text>", "pass": true|false, "notes": "<engineering analysis>"}},
          ...
        ],
        "warnings": ["<critical electrical issues or code violations>"],
        "recommendations": ["<engineering suggestions for improvement>"],
        "system_analysis": {{
          "system_type": "<DELTA or WYE, with explanation>",
          "grounding": "<grounded/ungrounded with rationale>",
          "phase_balance": "<analysis of phase loading balance>",
          "conductor_adequacy": "<assessment of conductor sizing>",
          "panel_usage": "<insights on application and location suitability>",
          "kva_calculation": "<total KVA with calculation shown>"
        }},
        "summary": "<brief paragraph summarizing overall electrical design quality and key findings>",
        "ok_to_build": true|false
      }}

      ### ENGINEERING RULES:
      1. Calculate phase balance: phases should be within ±20% of each other
      2. Verify conductor sizing meets NEC Table 310.15(B)(16) for given ampacity
      3. Check if MCB (Main Circuit Breaker) exceeds Main Bus Amps - this is a critical error
      4. Validate that total connected load per phase doesn't exceed main bus rating
      5. For 3-phase systems, verify neutral is sized per NEC 220.61
      6. Identify any circuits where breaker size doesn't protect conductor adequately
      7. Consider environmental factors based on location (wet, hazardous, outdoor, etc.)
      
      ### ANALYSIS REQUIREMENTS:
      - Show KVA calculation: KVA = (Voltage × Total_Amps × √3) / 1000 for 3-phase
      - Calculate phase imbalance percentage: max((|A-avg|, |B-avg|, |C-avg|)) / avg × 100
      - Verify ground conductor size per NEC 250.122
      - Assess if panel location requires special enclosure (NEMA 3R, 4X, etc.)
      
      IMPORTANT: Set ok_to_build=false if ANY critical electrical safety issues exist.
    """).strip()

    client = OpenAI(api_key=_API_KEY)
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
    import json
    try:
        data = json.loads(content)
    except Exception:
        data = {"items": [], "warnings": ["LLM returned non-JSON"], "ok_to_build": False, "__raw__": content}
    
    # Guardrail: always present required fields
    data.setdefault("items", [])
    data.setdefault("warnings", [])
    data.setdefault("recommendations", [])
    data.setdefault("system_analysis", {})
    data.setdefault("summary", "")
    data.setdefault("ok_to_build", False)
    
    return data
