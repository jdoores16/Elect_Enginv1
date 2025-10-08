
import os, json, logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

SCHEMA = {
  "type": "object",
  "properties": {
    "task": {"type": "string", "enum": ["one_line","power_plan","lighting_plan","revit_package"]},
    "project": {"type": "string"},
    "service_voltage": {"type": "string"},
    "service_amperes": {"type": "integer"},
    "panels": {"type": "array", "items": {"type": "object",
      "properties": {"name":{"type":"string"},"voltage":{"type":"string"},"bus_amperes":{"type":"integer"}},
      "required": ["name","voltage","bus_amperes"]
    }},
    "loads": {"type": "array", "items": {"type":"object",
      "properties": {"name":{"type":"string"},"kva":{"type":"number"},"panel":{"type":"string"}},
      "required": ["name","kva","panel"]
    }},
    "rooms": {"type": "array", "items": {"type":"object",
      "properties": {"name":{"type":"string"},"x":{"type":"number"},"y":{"type":"number"},"w":{"type":"number"},"h":{"type":"number"}},
      "required": ["name","x","y","w","h"]
    }},
    "devices": {"type": "array", "items": {"type":"object",
      "properties": {"tag":{"type":"string"},"x":{"type":"number"},"y":{"type":"number"},"notes":{"type":"string"}},
      "required": ["tag","x","y"]
    }},
    "notes": {"type": "string"}
  },
  "required": ["task","project"]
}

def _list_bucket(bucket_dir: str) -> List[str]:
    from pathlib import Path
    p = Path(bucket_dir)
    return [f.name for f in p.iterdir() if f.is_file()] if p.exists() else []

SYSTEM_PROMPT = (
  "You are a PE electrical design assistant. You must:\n"
  "1) Read the user command and the list of available project files.\n"
  "2) Produce STRICT JSON that matches the provided schema (no commentary).\n"
  "3) If the task is ambiguous, make conservative assumptions and proceed.\n"
  "4) Do not include any units in numeric fields; put notes in 'notes'.\n"
  "5) Coordinates are in drawing units (feet)."
)

def summarize_intent(user_text: str) -> str:
    if not OPENAI_API_KEY:
        logger.info("OpenAI API key not configured. Using fallback intent summarization.")
        return f"I understand that you want: {user_text[:160]}"
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role":"system","content":"Summarize the user's request in one concise sentence starting with 'I understand that you want…'"},
                {"role":"user","content": user_text}
            ],
            temperature=0.2
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f"OpenAI API error during intent summarization: {e.__class__.__name__}: {e}. Using fallback.")
        return f"I understand that you want: {user_text[:160]}"

def plan_from_prompt(user_text: str, bucket_dir: str) -> Dict[str, Any]:
    files = _list_bucket(bucket_dir)
    if not OPENAI_API_KEY:
        logger.warning("OpenAI API key not configured. Using hardcoded fallback plan. Configure OPENAI_API_KEY for AI-powered planning.")
        return {
          "task": "one_line",
          "project": "Demo Project",
          "service_voltage": "480Y/277V",
          "service_amperes": 2000,
          "panels": [{"name":"MDS","voltage":"480Y/277V","bus_amperes":1200}],
          "loads": [{"name":"CHWP-1","kva":50,"panel":"MDS"}],
          "notes": "Fallback plan used due to missing OPENAI_API_KEY."
        }
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        user = (
          f"Command: {user_text}\n"
          f"Available files: {files}\n"
          f"Return ONLY JSON conforming to this schema: {json.dumps(SCHEMA)}"
        )
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":SYSTEM_PROMPT},{"role":"user","content":user}],
            response_format={"type": "json_object"},
            temperature=0.2
        )
        data = json.loads(resp.choices[0].message.content)
        data["project"] = data.get("project") or "Untitled Project"
        data["task"] = data.get("task") or "one_line"
        return data
    except json.JSONDecodeError as e:
        logger.error(f"OpenAI returned invalid JSON: {e}. Using fallback plan.")
        return {
          "task": "one_line",
          "project": "Fallback (Invalid AI Response)",
          "service_voltage": "480Y/277V",
          "service_amperes": 2000,
          "panels": [{"name":"MDS","voltage":"480Y/277V","bus_amperes":1200}],
          "loads": [{"name":"GEN-1","kva":25,"panel":"MDS"}],
          "notes": f"AI returned invalid JSON format."
        }
    except Exception as e:
        logger.error(f"OpenAI API error during plan generation: {e.__class__.__name__}: {e}. Using fallback plan.")
        return {
          "task": "one_line",
          "project": "Fallback (LLM error)",
          "service_voltage": "480Y/277V",
          "service_amperes": 2000,
          "panels": [{"name":"MDS","voltage":"480Y/277V","bus_amperes":1200}],
          "loads": [{"name":"GEN-1","kva":25,"panel":"MDS"}],
          "notes": f"LLM error: {e.__class__.__name__}"
        }
