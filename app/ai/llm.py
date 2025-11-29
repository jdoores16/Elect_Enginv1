# app/ai/llm.py
# LLM service wrapper with safe config, retries, and concise helper functions.

import json
import logging
import time
from typing import Any, Dict, List, Optional

from openai import OpenAI
from openai._exceptions import RateLimitError, APIConnectionError, APIStatusError, AuthenticationError

# Import the central settings manager so this module stays in sync with .env
from app.core.settings import settings

logger = logging.getLogger(__name__)

# ---- Client construction (single instance) ----
# Best practice: build one client per process. This reduces overhead, and is easier to test/mocking.
client = OpenAI(
    api_key=settings.effective_api_key,     # supports both direct OpenAI and Replit AI Integrations
    base_url=settings.effective_base_url,   # optional: for Replit AI Integrations
    organization=settings.OPENAI_ORG_ID, # optional
    project=settings.OPENAI_PROJECT,     # optional
    timeout=settings.OPENAI_TIMEOUT_S,   # best practice: prevent hung requests
)

DEFAULT_MODEL = settings.OPENAI_MODEL  # centralize model selection

# --------------------------
# Health: quick auth check
# --------------------------
def test_auth() -> bool:
    """
    Verifies that the OpenAI API key is valid by attempting a tiny call (list models).
    Returns True if authentication works, False otherwise.
    """
    try:
        client.models.list()
        logger.info("OpenAI authentication successful.")
        return True
    except Exception as e:
        logger.error(f"OpenAI authentication failed: {e}")
        return False


# --------------------------
# Lite retry wrapper
# --------------------------
def _chat_with_retries(
    *,
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 512,
    response_format: Optional[Dict[str, str]] = None,
    user: Optional[str] = None,
    max_retries: int = 2,
    backoff_s: float = 0.75,
):
    """
    Best practice:
    - Retry only on transient errors (rate limits, connection issues).
    - Fail fast on auth/config problems.
    - Keep deterministic defaults (low temperature) for production paths.
    """
    mdl = model or DEFAULT_MODEL
    attempt = 0
    last_err: Optional[Exception] = None

    while attempt <= max_retries:
        try:
            return client.chat.completions.create(
                model=mdl,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
                user=user,
            )
        except (RateLimitError, APIConnectionError) as e:
            last_err = e
            delay = backoff_s * (2 ** attempt)
            logger.warning(f"Transient LLM error (attempt {attempt+1}/{max_retries+1}): {e}. Backing off {delay:.2f}s")
            time.sleep(delay)
            attempt += 1
        except AuthenticationError as e:
            # Fail fast on auth issues
            logger.error("Authentication error with OpenAI: %s", e)
            raise
        except APIStatusError as e:
            # 4xx/5xx – usually non-transient for our payloads. Don't loop forever.
            last_err = e
            logger.error("OpenAI API status error: %s", e)
            break
        except Exception as e:
            last_err = e
            logger.exception("Unexpected LLM error: %s", e)
            break

    raise RuntimeError(f"LLM call failed after {attempt} attempts: {last_err}")

# --------------------------
# Prompts / Schema
# --------------------------
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

# --------------------------
# Helpers
# --------------------------
def _list_bucket(bucket_dir: str) -> List[str]:
    from pathlib import Path
    p = Path(bucket_dir)
    return [f.name for f in p.iterdir() if f.is_file()] if p.exists() else []

# --------------------------
# Public API
# --------------------------
def summarize_intent(user_text: str) -> str:
    """
    Return a brief, 3–5 word confirmation like 'Got it' or 'Understood'.
    Best practice: reuse the module-level client; keep low temp.
    """
    try:
        resp = _chat_with_retries(
            messages=[
                {"role": "system", "content": "Respond with a brief 3-5 word confirmation like 'Got it' or 'Understood'. Be extremely concise."},
                {"role": "user", "content": user_text},
            ],
            model=DEFAULT_MODEL,
            temperature=0.2,
            max_tokens=16,
        )
        if not resp.choices:
            logger.error("LLM returned no choices for summarize_intent.")
            return "Got it."
        return (resp.choices[0].message.content or "").strip() or "Got it."
    except Exception as e:
        logger.warning(f"OpenAI API error during intent summarization: {e.__class__.__name__}: {e}. Using fallback.")
        return "Got it."
    
def extract_circuit_from_text(user_text: str) -> Dict[str, Any]:
    """
    Extract circuit information from voice/text input.
    Returns dict with keys: circuit_numbers, pole_spaces, description, poles, breaker_amps, load_amps
    Returns empty dict if no circuit data found.
    
    Example: "circuit 1 is a 20A/1P breaker and feeds and exhaust fan at 8A"
    Returns: {'circuit_numbers': '1', 'pole_spaces': [1], 'poles': 1, 'breaker_amps': 20, 'load_amps': 8, 'description': 'EXHAUST FAN'}
    
    Example: "circuit 3,5 is a 30A/2P circuit that feeds a cold water pump in the basement and the full load is 18A"
    Returns: {'circuit_numbers': '3,5', 'pole_spaces': [3, 5], 'poles': 2, 'breaker_amps': 30, 'load_amps': 18, 'description': 'BASEMENT COLD WATER PUMP'}
    """
    import re
    
    circuit_data = {}
    text_lower = user_text.lower()
    
    # Look for circuit number patterns with multiple separators: comma, slash, space, hyphen
    # Matches: "circuit 1", "circuits 1,3,5", "circuit 2/4/6", "circuit 2 4 6", etc.
    circuit_num_match = re.search(r'(?:circuit|ckt|pole\s+space)s?\s+([\d,/\s-]+)', text_lower)
    if not circuit_num_match:
        return {}  # Not circuit-related input
    
    circuit_nums_raw = circuit_num_match.group(1).strip()
    circuit_data['circuit_numbers'] = circuit_nums_raw
    
    # Parse pole spaces into a list of integers, handling multiple separators
    # Split on comma, slash, space, or hyphen
    pole_spaces = [int(n.strip()) for n in re.split(r'[,/\s-]+', circuit_nums_raw) if n.strip().isdigit()]
    circuit_data['pole_spaces'] = pole_spaces
    
    # Combined breaker format: "20A/1P" or "30AF/2P"
    combined_match = re.search(r'(\d+)\s*a[f]?/(\d+)\s*p', text_lower)
    if combined_match:
        circuit_data['breaker_amps'] = int(combined_match.group(1))
        circuit_data['poles'] = int(combined_match.group(2))
    else:
        # Poles: "1 pole", "3-pole", "2P"
        poles_match = re.search(r'(\d+)[\s-]*p(?:ole)?(?:s)?\b', text_lower)
        if poles_match:
            circuit_data['poles'] = int(poles_match.group(1))
        
        # Breaker amps: "20A breaker", "30 amp"
        breaker_match = re.search(r'(?:breaker(?:\s+amp(?:s|ere)?)?|amp(?:s|ere)?)[\s:]*(\d+)\s*a?|(\d+)\s*a(?:mp)?(?:\s+breaker)', text_lower)
        if breaker_match:
            circuit_data['breaker_amps'] = int(breaker_match.group(1) or breaker_match.group(2))
    
    # Load amps: "at 8A", "feeds at 8 amps", "load is 10A", "with a load of 40A", "load of 40A"
    load_match = re.search(r'(?:at|load(?:\s+is|\s+of)?|draws?|with\s+a\s+load\s+of)[\s:]*(\d+(?:\.\d+)?)\s*a(?:mp(?:s|ere)?)?', text_lower)
    if load_match:
        circuit_data['load_amps'] = float(load_match.group(1))
    else:
        # Also check for "phase amp" patterns as fallback
        phase_amps_match = re.search(r'(?:phase\s+amp(?:s)?(?:\s+is)?\s+|per\s+phase\s+)(\d+(?:\.\d+)?)', text_lower)
        if phase_amps_match:
            circuit_data['load_amps'] = float(phase_amps_match.group(1))
    
    # Description: extract from various patterns
    # Pattern 1: "feeding [a] <description>" - matches "feeding a rooftop MAU unit"
    desc_match = re.search(r'feeding\s+(?:a|an|the)?\s*(.+?)\s+(?:and\s+the\s+)?(?:with|load|at|\d+)', text_lower)
    if desc_match:
        desc_text = desc_match.group(1).strip()
        circuit_data['description'] = desc_text.strip().upper()
    else:
        # Pattern 2: "feeds [a] <description> in <location>" or "feeds [a] <description> at <load>"
        desc_match = re.search(r'feeds?\s+(?:and\s+)?(?:a|an|the)?\s*(.+?)\s+(?:and\s+the\s+)?(?:full\s+)?(?:load|at|with|\d+)', text_lower)
        if desc_match:
            desc_text = desc_match.group(1).strip()
            circuit_data['description'] = desc_text.strip().upper()
        else:
            # Pattern 3: "is [a] <description> [and/with]"
            desc_match = re.search(r'is\s+(?:a|an|for)?\s*([^,]+?)\s+(?:and|with|at|\d+\s*a)', text_lower)
            if desc_match:
                desc_text = desc_match.group(1).strip()
                # Remove breaker/pole info from description
                desc_text = re.sub(r'\d+\s*a[f]?/\d+\s*p\s+(?:breaker|circuit)', '', desc_text, flags=re.IGNORECASE)
                desc_text = re.sub(r'\d+[\s-]*p(?:ole)?\s+(?:breaker|circuit)', '', desc_text, flags=re.IGNORECASE)
                desc_text = re.sub(r'\d+\s*a(?:mp)?\s+(?:breaker|circuit)', '', desc_text, flags=re.IGNORECASE)
                desc_text = desc_text.strip()
                if desc_text:
                    circuit_data['description'] = desc_text.upper()
    
    logger.info(f"Extracted circuit data from regex: {circuit_data}")
    return circuit_data


def extract_circuit_from_text_llm(user_text: str) -> Dict[str, Any]:
    """
    Use OpenAI LLM to extract circuit information from natural language.
    More robust than regex for complex or conversational inputs.
    
    Returns dict with keys: circuit_numbers, pole_spaces, description, poles, breaker_amps, load_amps
    Returns empty dict if no circuit data found or if API key is not configured.
    
    Example: "circuit 1 is a 20A/1P breaker and feeds and exhaust fan at 8A"
    Returns: {'circuit_numbers': '1', 'pole_spaces': [1], 'poles': 1, 'breaker_amps': 20, 'load_amps': 8, 'description': 'EXHAUST FAN'}
    
    Example: "circuit 3,5 is a 30A/2P circuit that feeds a cold water pump in the basement and the full load is 18A"
    Returns: {'circuit_numbers': '3,5', 'pole_spaces': [3, 5], 'poles': 2, 'breaker_amps': 30, 'load_amps': 18, 'description': 'BASEMENT COLD WATER PUMP'}
    """
    if not settings.OPENAI_API_KEY:
        logger.info("OpenAI API key not configured. Skipping LLM circuit extraction.")
        return {}
    
    try:
        system_prompt = """You are a circuit data extraction assistant. Extract circuit information from user input and return STRICT JSON.

Output format:
{
  "circuit_numbers": "circuit numbers as they appear in input (e.g., '1' or '3,5' or '2/4/6')",
  "pole_spaces": [array of integers representing pole space numbers],
  "poles": integer (1, 2, or 3),
  "breaker_amps": float (breaker rating in amps),
  "load_amps": float (actual load in amps),
  "description": "brief uppercase description of load including location if mentioned"
}

Rules:
- If no circuit mentioned, return {}
- circuit_numbers preserves the original separator format from user input
- pole_spaces is always an array of integers (e.g., [3, 5] or [2, 4, 6])
- Pole spaces can be separated by commas, slashes, spaces, or hyphens in the input
- For "circuit 2/4/6", circuit_numbers="2/4/6" AND pole_spaces=[2, 4, 6]
- Extract all numeric values accurately
- Description should include location if mentioned (e.g., 'ROOFTOP MAU UNIT')
- Remove articles (a, an, the) and breaker/circuit keywords from description
- load_amps should be the actual load, not breaker rating
- Keep descriptions concise but meaningful (max 39 characters)
"""
        
        resp = _chat_with_retries(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            model=DEFAULT_MODEL,
            temperature=0.0,  # Deterministic for data extraction
            max_tokens=150,
            response_format={"type": "json_object"},
        )
        
        if not resp.choices:
            logger.warning("LLM returned no choices for circuit extraction.")
            return {}
        
        content = (resp.choices[0].message.content or "").strip()
        if not content:
            return {}
        
        data = json.loads(content)
        logger.info(f"Extracted circuit data from LLM: {data}")
        return data
        
    except Exception as e:
        logger.warning(f"LLM circuit extraction failed: {e.__class__.__name__}: {e}")
        return {}


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
    
    # Phase patterns: "3 phase", "3ph", "3-ph", "single phase", "1-phase", "phase is 3", "phase: 3"
    phase_match = re.search(r'(?:phase\s*(?:is|:)?\s*(\d+|single|three|one)|(\d+|single|three|one)[\s-]*(?:phase|ph)\b)', text_lower)
    if phase_match:
        phase_val = phase_match.group(1) or phase_match.group(2)
        if phase_val in ['three', '3']:
            specs['phase'] = '3'
        elif phase_val in ['single', 'one', '1']:
            specs['phase'] = '1'
        else:
            specs['phase'] = phase_val
        logger.info(f"Extracted phase: {specs['phase']}")
    
    # Wire patterns: "4 wire", "3W", "wire is 4", "wire: 4"
    wire_match = re.search(r'(?:wire\s*(?:is|:)?\s*(\d+)|(\d+)\s*w(?:ire)?)', text_lower)
    if wire_match:
        specs['wire'] = wire_match.group(1) or wire_match.group(2)
        logger.info(f"Extracted wire: {specs['wire']}")
    
    # Main bus amps patterns: "400A", "400 amps", "main bus amps 400", "bus amps 400"
    # MUST have "bus" or "main" keyword to avoid matching circuit breaker amps
    bus_amps_match = re.search(r'(?:main\s+bus(?:\s+amp(?:s|ere)?)?|bus\s+amp(?:s|ere)?)[\s:]+(\d+)\s*a?(?:mp(?:s|ere)?)?', text_lower)
    if bus_amps_match:
        specs['main_bus_amps'] = bus_amps_match.group(1)
        logger.info(f"Extracted main_bus_amps: {specs['main_bus_amps']}")
    
    # Main breaker: "100AF/70AT" or "MLO" (Main Lug Only)
    # Check for MLO first (specific pattern)
    if re.search(r'\bMLO\b|main\s+lug\s+only', user_text, re.IGNORECASE):
        specs['main_breaker'] = 'MLO'
        logger.info(f"Extracted main_breaker: MLO (Main Lug Only)")
    else:
        # Then check for standard breaker ratings
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


def _keyword_based_fallback(user_text: str, files: List[str], reason: str = "") -> Dict[str, Any]:
    """Keyword-based fallback plan when LLM is not available or fails."""
    import re
    text_lower = user_text.lower().strip()
    task = None
    
    if any(kw in text_lower for kw in ["panel schedule", "panelboard schedule", "panel board schedule", "panelboard", "panel board", "circuit schedule"]):
        task = "panel_schedule"
    elif any(kw in text_lower for kw in ["power plan", "receptacle plan", "outlet plan", "power layout"]):
        task = "power_plan"
    elif any(kw in text_lower for kw in ["lighting plan", "light plan", "fixture plan", "illumination plan"]):
        task = "lighting_plan"
    elif any(kw in text_lower for kw in ["revit", "dynamo", "bim"]):
        task = "revit_package"
    elif any(kw in text_lower for kw in ["one line", "oneline", "one-line", "single line"]):
        task = "one_line"
    else:
        task = "panel_schedule"
    
    number_of_ckts = None
    panel_name = None
    
    num_match = re.search(r'\b(\d+)\s*(?:circuits?|ckts?|spaces?)?\b', text_lower)
    if num_match:
        try:
            num = int(num_match.group(1))
            if 18 <= num <= 84:
                number_of_ckts = num if num % 2 == 0 else num + 1
                logger.info(f"Extracted number_of_ckts={number_of_ckts} from text")
        except ValueError:
            pass
    
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
        "notes": f"Keyword-based fallback (detected: {task}). {reason}"
    }
    if number_of_ckts:
        plan["number_of_ckts"] = number_of_ckts
    if panel_name:
        plan["panel_name"] = panel_name
    return plan


def plan_from_prompt(user_text: str, bucket_dir: str) -> Dict[str, Any]:
    """
    Main planner: sends the schema + files to the LLM and expects JSON back.
    Falls back to a keyword-based plan if the LLM call fails.
    """
    files = _list_bucket(bucket_dir)
    
    try:
        user = (
          f"Command: {user_text}\n"
          f"Available files: {files}\n"
          f"Return ONLY JSON conforming to this schema: {json.dumps(SCHEMA)}"
        )
        resp = client.chat.completions.create(
            model=DEFAULT_MODEL,
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
        return _keyword_based_fallback(user_text, files, "AI returned invalid JSON format.")
    except Exception as e:
        logger.error(f"OpenAI API error during plan generation: {e.__class__.__name__}: {e}. Using keyword-based fallback.")
        return _keyword_based_fallback(user_text, files, f"LLM error: {e.__class__.__name__}")
