"""
AI-enhanced OCR extraction using OpenAI LLM.
Provides intelligent fallback for poorly formatted, handwritten, or unusual text patterns.
"""

import logging
from typing import List, Dict, Optional
import json
from openai import OpenAI
from app.core.settings import get_settings

logger = logging.getLogger(__name__)


def ai_extract_circuits(ocr_lines: List[str], panel_name: Optional[str] = None) -> List[Dict]:
    """
    Use OpenAI to extract circuit data from OCR text when regex parsing fails or produces low confidence.
    
    Args:
        ocr_lines: List of text lines from OCR
        panel_name: Optional panel name for context
        
    Returns:
        List of circuit dictionaries with: number, description, load, breaker_amps, breaker_poles
    """
    settings = get_settings()
    
    if not settings.openai_api_key:
        logger.warning("OpenAI API key not configured, skipping AI extraction")
        return []
    
    try:
        client = OpenAI(api_key=settings.openai_api_key)
        
        ocr_text = '\n'.join(ocr_lines)
        
        system_prompt = """You are an expert electrical engineer analyzing panelboard schedules.
Extract circuit information from OCR text that may contain errors, poor formatting, or handwritten notes.

For each circuit found, extract:
- number: Circuit number (1-84)
- description: What the circuit powers (e.g., "LIGHTING", "RECEPTACLES", "HVAC UNIT")
- load: Load in kVA, kW, VA, W, or A (just the number with unit)
- breaker_amps: Breaker ampacity rating (15, 20, 30, etc.)
- breaker_poles: Number of poles (1, 2, or 3)

Return ONLY a JSON array of circuits. If you can't determine a value, omit that field.
Example: [{"number": "1", "description": "LIGHTING", "load": "2.5kVA", "breaker_amps": "20", "breaker_poles": "1"}]

Be flexible with formatting - OCR may have:
- Misspellings (LIGHTNG → LIGHTING)
- Missing spaces (LIGHTING2.5kVA20A → separate these)
- Extra characters (#1 → 1, Ckt 5 → 5)
- Handwritten notes or abbreviations"""

        user_prompt = f"""Extract circuits from this panelboard OCR text{"for panel " + panel_name if panel_name else ""}:

{ocr_text[:3000]}

Return circuits as JSON array."""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=2000
        )
        
        response_text = response.choices[0].message.content.strip()
        
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        circuits = json.loads(response_text)
        
        if not isinstance(circuits, list):
            logger.error(f"AI response is not a list: {type(circuits)}")
            return []
        
        logger.info(f"AI extracted {len(circuits)} circuits from OCR text")
        return circuits
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response as JSON: {e}")
        logger.debug(f"AI response: {response_text[:500]}")
        return []
    except Exception as e:
        logger.error(f"AI circuit extraction failed: {e}", exc_info=True)
        return []


def ai_extract_panel_specs(ocr_lines: List[str]) -> Dict[str, str]:
    """
    Use OpenAI to extract panel specifications from OCR text.
    
    Args:
        ocr_lines: List of text lines from OCR
        
    Returns:
        Dictionary of panel specifications
    """
    settings = get_settings()
    
    if not settings.openai_api_key:
        logger.warning("OpenAI API key not configured, skipping AI extraction")
        return {}
    
    try:
        client = OpenAI(api_key=settings.openai_api_key)
        
        ocr_text = '\n'.join(ocr_lines)
        
        system_prompt = """You are an expert electrical engineer analyzing panelboard nameplates and schedules.
Extract panel specifications from OCR text that may contain errors or poor formatting.

Extract these fields if present:
- panel_name: Panel identifier (e.g., "PP-1", "LP-2A", "PANEL-01")
- voltage: Voltage rating (e.g., "480Y/277V", "208V", "120/240V")
- phase: Number of phases (1 or 3)
- wire: Wire configuration (e.g., "4W+G", "3W", "4-wire")
- main_bus_amps: Main bus ampacity (e.g., "800", "400A")
- main_breaker: Main breaker rating (e.g., "800A", "MLO", "600AF")
- mounting: Mounting type (e.g., "SURFACE", "FLUSH", "RECESSED")
- feed: Where panel is fed from (e.g., "MSB", "UPSTREAM PANEL")
- location: Physical location (e.g., "ELECTRICAL ROOM", "1ST FLOOR")

Return ONLY a JSON object. If you can't determine a value, omit that field.
Be flexible with OCR errors and abbreviations."""

        user_prompt = f"""Extract panel specifications from this OCR text:

{ocr_text[:2000]}

Return as JSON object."""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=1000
        )
        
        response_text = response.choices[0].message.content.strip()
        
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        specs = json.loads(response_text)
        
        if not isinstance(specs, dict):
            logger.error(f"AI response is not a dict: {type(specs)}")
            return {}
        
        logger.info(f"AI extracted {len(specs)} panel specifications")
        return specs
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response as JSON: {e}")
        logger.debug(f"AI response: {response_text[:500]}")
        return {}
    except Exception as e:
        logger.error(f"AI panel spec extraction failed: {e}", exc_info=True)
        return {}


def merge_regex_and_ai_results(regex_circuits: List[Dict], ai_circuits: List[Dict]) -> List[Dict]:
    """
    Intelligently merge results from regex parsing and AI extraction.
    Regex results are preferred (more reliable), AI fills in gaps.
    
    Args:
        regex_circuits: Circuits extracted via regex patterns
        ai_circuits: Circuits extracted via AI
        
    Returns:
        Merged list of circuits with best data from both sources
    """
    regex_by_num = {int(c['number']): c for c in regex_circuits if c.get('number', '').isdigit()}
    ai_by_num = {int(c['number']): c for c in ai_circuits if c.get('number', '').isdigit()}
    
    all_circuit_nums = set(regex_by_num.keys()) | set(ai_by_num.keys())
    
    merged = []
    for num in sorted(all_circuit_nums):
        regex_data = regex_by_num.get(num, {})
        ai_data = ai_by_num.get(num, {})
        
        circuit = {'number': str(num)}
        
        for field in ['description', 'load', 'breaker_amps', 'breaker_poles']:
            regex_val = regex_data.get(field)
            ai_val = ai_data.get(field)
            
            if regex_val and regex_val != 'MISSING':
                circuit[field] = regex_val
            elif ai_val and ai_val != 'MISSING':
                circuit[field] = ai_val
            else:
                circuit[field] = 'MISSING'
        
        merged.append(circuit)
    
    logger.info(f"Merged {len(merged)} circuits from regex ({len(regex_circuits)}) and AI ({len(ai_circuits)})")
    
    return merged
