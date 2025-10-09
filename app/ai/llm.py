
import os, json, logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

SCHEMA = {
  "type": "object",
  "properties": {
    "task": {"type": "string", "enum": ["one_line","power_plan","lighting_plan","revit_package","panel_schedule"]},
    "project": {"type": "string"},
    "service_voltage": {"type": "string"},
    "service_amperes": {"type": "integer"},
    "number_of_ckts": {"type": "integer", "minimum": 18, "maximum": 84, "description": "Number of circuits for panel schedule (must be even, 18-84)"},
    "panel_name": {"type": "string", "description": "Panel identifier/name for panel schedule (e.g., PP-TEST1, Panel A, LP-1)"},
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
  "5) Coordinates are in drawing units (feet).\n"
  "6) For panel_schedule tasks, extract ALL parameters from user text:\n"
  "   - 'number_of_ckts': Extract from phrases like '42 circuits', 'forty-two', '42' (must be even, 18-84)\n"
  "   - 'panel_name': Extract from phrases like 'panel name is PP-TEST1', 'panel PP-1', 'called LP-A'\n"
  "   - Extract any other panel specifications mentioned (voltage, phase, amperes, etc.)\n"
  "7) Look for parameters in ANY user input, not just initial commands. Users may provide missing info in follow-up messages."
)

def summarize_intent(user_text: str) -> str:
    if not OPENAI_API_KEY:
        logger.info("OpenAI API key not configured. Using fallback intent summarization.")
        return "Got it."
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role":"system","content":"Respond with a brief 3-5 word confirmation like 'Got it' or 'Understood'. Be extremely concise."},
                {"role":"user","content": user_text}
            ],
            temperature=0.2
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f"OpenAI API error during intent summarization: {e.__class__.__name__}: {e}. Using fallback.")
        return "Got it."

def extract_panel_specs_from_text(user_text: str) -> Dict[str, str]:
    """
    Extract panel specifications from voice/text input.
    Similar to OCR extraction but for conversational input.
    Returns dict with keys: voltage, phase, wire, main_bus_amps, main_breaker, mounting, feed, location
    """
    import re
    
    specs = {}
    text_lower = user_text.lower()
    
    # Voltage patterns: "480/277V", "480 volt", "208V"
    voltage_match = re.search(r'(\d+(?:/\d+)?)\s*v(?:olt(?:s|age)?)?', text_lower)
    if voltage_match:
        specs['voltage'] = voltage_match.group(1).upper() + 'V'
        logger.info(f"Extracted voltage: {specs['voltage']}")
    
    # Phase patterns: "3 phase", "single phase", "1-phase"
    phase_match = re.search(r'(?:(\d+|single|three|one)[\s-]*phase)', text_lower)
    if phase_match:
        phase_val = phase_match.group(1)
        if phase_val in ['three', '3']:
            specs['phase'] = '3'
        elif phase_val in ['single', 'one', '1']:
            specs['phase'] = '1'
        else:
            specs['phase'] = phase_val
        logger.info(f"Extracted phase: {specs['phase']}")
    
    # Wire patterns: "4 wire", "3W"
    wire_match = re.search(r'(\d+)\s*w(?:ire)?', text_lower)
    if wire_match:
        specs['wire'] = wire_match.group(1)
        logger.info(f"Extracted wire: {specs['wire']}")
    
    # Main bus amps patterns: "400A", "400 amps"
    bus_amps_match = re.search(r'(?:main\s+bus\s+|bus\s+)?(\d+)\s*a(?:mp(?:s|ere)?)?', text_lower)
    if bus_amps_match:
        specs['main_bus_amps'] = bus_amps_match.group(1)
        logger.info(f"Extracted main_bus_amps: {specs['main_bus_amps']}")
    
    # Main breaker: "100AF/70AT"
    breaker_match = re.search(r'(?:main\s+breaker|breaker|mcb)[\s:]*([A-Z0-9/]+)', user_text, re.IGNORECASE)
    if breaker_match:
        specs['main_breaker'] = breaker_match.group(1).upper()
        logger.info(f"Extracted main_breaker: {specs['main_breaker']}")
    
    # Mounting: "flush", "surface", "recess"
    mounting_match = re.search(r'(flush|surface|recess(?:ed)?)\s*mount', text_lower)
    if mounting_match:
        specs['mounting'] = mounting_match.group(1).upper()
        logger.info(f"Extracted mounting: {specs['mounting']}")
    
    # Feed from: "MDP", "panel A"
    feed_match = re.search(r'(?:feed\s+from|fed\s+from)[\s:]*([A-Z0-9\s\-]+)', user_text, re.IGNORECASE)
    if feed_match:
        specs['feed'] = feed_match.group(1).strip()
        logger.info(f"Extracted feed: {specs['feed']}")
    
    # Location: "room 101", "first floor"
    location_match = re.search(r'(?:location|located\s+(?:in|at))[\s:]*([^,.]+)', text_lower)
    if location_match:
        specs['location'] = location_match.group(1).strip().title()
        logger.info(f"Extracted location: {specs['location']}")
    
    return specs


def plan_from_prompt(user_text: str, bucket_dir: str) -> Dict[str, Any]:
    files = _list_bucket(bucket_dir)
    if not OPENAI_API_KEY:
        logger.warning("OpenAI API key not configured. Using keyword-based fallback. Configure OPENAI_API_KEY for AI-powered planning.")
        
        # Keyword detection for task type
        text_lower = user_text.lower()
        task = "one_line"  # default
        
        if any(kw in text_lower for kw in ["panel schedule", "panelboard schedule", "panelboard", "panel board", "schedule", "circuit schedule"]):
            task = "panel_schedule"
        elif any(kw in text_lower for kw in ["power plan", "receptacle", "outlet", "power layout"]):
            task = "power_plan"
        elif any(kw in text_lower for kw in ["lighting plan", "light", "fixture", "illumination"]):
            task = "lighting_plan"
        elif any(kw in text_lower for kw in ["revit", "dynamo", "bim"]):
            task = "revit_package"
        elif any(kw in text_lower for kw in ["one line", "oneline", "one-line", "service", "feeder"]):
            task = "one_line"
        
        # Extract parameters if present in text
        import re
        number_of_ckts = None
        panel_name = None
        
        # Look for patterns like "42", "42 circuits", "forty-two"
        num_match = re.search(r'\b(\d+)\s*(?:circuits?|ckts?|spaces?)?\b', text_lower)
        if num_match:
            try:
                num = int(num_match.group(1))
                # Validate and round to even number within range
                if 18 <= num <= 84:
                    number_of_ckts = num if num % 2 == 0 else num + 1
                    logger.info(f"Extracted number_of_ckts={number_of_ckts} from text")
            except ValueError:
                pass
        
        # Look for panel name patterns - only explicit panel-specific phrases to avoid false positives
        # Allow alphanumeric, spaces, hyphens in panel names (e.g., "Panel A", "PP-TEST1", "LP 1A")
        panel_patterns = [
            r'panel\s+name\s+(?:is\s+)?([A-Z0-9][A-Z0-9\-\s]*[A-Z0-9]|[A-Z0-9])',
            r'panel\s+(?:is\s+)?called\s+([A-Z0-9][A-Z0-9\-\s]*[A-Z0-9]|[A-Z0-9])',
            r'panel\s+(?:is\s+)?named\s+([A-Z0-9][A-Z0-9\-\s]*[A-Z0-9]|[A-Z0-9])',
            r'panel\s+identifier\s+(?:is\s+)?([A-Z0-9][A-Z0-9\-\s]*[A-Z0-9]|[A-Z0-9])'
        ]
        for pattern in panel_patterns:
            match = re.search(pattern, user_text, re.IGNORECASE)
            if match:
                panel_name = match.group(1).strip().upper()
                logger.info(f"Extracted panel_name={panel_name} from text")
                break
        
        plan = {
          "task": task,
          "project": "Demo Project",
          "service_voltage": "480Y/277V",
          "service_amperes": 2000,
          "panels": [{"name":"MDS","voltage":"480Y/277V","bus_amperes":1200}],
          "loads": [{"name":"CHWP-1","kva":50,"panel":"MDS"}],
          "notes": f"Keyword-based fallback (detected: {task}). Configure OPENAI_API_KEY for better parsing."
        }
        if number_of_ckts:
            plan["number_of_ckts"] = number_of_ckts
        if panel_name:
            plan["panel_name"] = panel_name
        return plan
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
