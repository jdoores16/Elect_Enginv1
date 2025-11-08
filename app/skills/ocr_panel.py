
from pathlib import Path
from typing import List, Tuple, Dict, Optional
import re
import logging
import pytesseract
from PIL import Image
import io

logger = logging.getLogger(__name__)

def ocr_image_to_lines(image_path: Path, use_preprocessing: bool = True, save_debug: bool = False) -> List[str]:
    """
    Extract text lines from an image using Tesseract OCR.
    
    Args:
        image_path: Path to image file
        use_preprocessing: If True, apply advanced image preprocessing for better accuracy
        save_debug: If True, save preprocessing debug images
        
    Returns:
        List of extracted text lines
    """
    try:
        if use_preprocessing:
            from app.skills.image_preprocessing import preprocess_for_ocr
            
            img = preprocess_for_ocr(image_path, aggressive=False, save_debug=save_debug)
            logger.info(f"Applied advanced preprocessing to {image_path.name}")
        else:
            img = Image.open(image_path)
            img = img.convert("L")
            logger.info(f"Using basic grayscale conversion for {image_path.name}")
        
        custom_config = r'--oem 3 --psm 6'
        
        text = pytesseract.image_to_string(img, config=custom_config)
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        logger.info(f"OCR extracted {len(lines)} lines from {image_path.name}")
        return lines
    except pytesseract.TesseractNotFoundError as e:
        logger.error(f"Tesseract OCR is not installed or not in PATH. Please install Tesseract. Error: {e}")
        raise
    except Exception as e:
        logger.error(f"Error during OCR processing of {image_path}: {e.__class__.__name__}: {e}")
        raise

# Enhanced regex to capture all circuit parameters
# Matches patterns like: "1 - Lighting - 2.5kVA - 20A 1P" or "2  Receptacles  1.8  15A  1P"
CIRCUIT_RE = re.compile(
    r"^(?P<num>\d{1,3})(?:[A-C]?)?\s*[-:.\s]?\s*(?P<desc>.+?)"
    r"(?:\s+(?P<load>[\d.]+)\s*(?:kVA|kW|VA|W|A)?)?"
    r"(?:\s+(?P<amps>\d{1,4})\s*A(?:mp)?s?)?"
    r"(?:\s+(?P<poles>[123])\s*P(?:ole)?)?.*$",
    re.IGNORECASE
)

def parse_circuits_from_lines(lines: List[str], number_of_ckts: int = None) -> List[Dict]:
    """
    Parse circuit information from OCR lines.
    Returns list of dicts with: number, description, load, breaker_amps, breaker_poles
    
    Args:
        lines: OCR text lines to parse
        number_of_ckts: Total number of circuits (18-84, even). If not provided, determined from max circuit found.
    
    Returns:
        Complete list of circuits 1-N with "MISSING" for any data not found in OCR
    """
    # First pass: extract circuits found in OCR
    found_circuits = {}
    skipped = 0
    max_circuit_num = 0
    
    for ln in lines:
        m = CIRCUIT_RE.match(ln)
        if m and m.group("num"):
            circuit_num = int(m.group("num").strip())
            max_circuit_num = max(max_circuit_num, circuit_num)
            found_circuits[circuit_num] = {
                'number': str(circuit_num),
                'description': m.group("desc").strip() if m.group("desc") else "MISSING",
                'load': m.group("load") if m.group("load") else "MISSING",
                'breaker_amps': m.group("amps") if m.group("amps") else "MISSING",
                'breaker_poles': m.group("poles") if m.group("poles") else "MISSING"
            }
        else:
            skipped += 1
    
    logger.info(f"Parsed {len(found_circuits)} circuits from {len(lines)} OCR lines. Skipped {skipped} non-matching lines.")
    
    # Determine total number of circuits
    if number_of_ckts is None:
        # Round up to nearest even number, clamped to 18-84
        number_of_ckts = max(18, min(84, ((max_circuit_num + 1) // 2) * 2))
        logger.info(f"Determined number_of_ckts={number_of_ckts} from max circuit {max_circuit_num}")
    else:
        # Validate and round to even number
        number_of_ckts = max(18, min(84, number_of_ckts))
        if number_of_ckts % 2 != 0:
            number_of_ckts += 1
        logger.info(f"Using specified number_of_ckts={number_of_ckts}")
    
    # Create complete list of circuits 1 through number_of_ckts
    circuits = []
    for i in range(1, number_of_ckts + 1):
        if i in found_circuits:
            circuits.append(found_circuits[i])
        else:
            # Circuit not found in OCR, create with MISSING values
            circuits.append({
                'number': str(i),
                'description': 'MISSING',
                'load': 'MISSING',
                'breaker_amps': 'MISSING',
                'breaker_poles': 'MISSING'
            })
    
    logger.info(f"Created complete circuit list with {number_of_ckts} circuits ({len(found_circuits)} from OCR, {number_of_ckts - len(found_circuits)} filled with MISSING)")
    
    return circuits

def extract_panel_specs(lines: List[str]) -> dict:
    """
    Extract panel specifications from OCR text lines.
    Looks for panel name, voltage, phase, wire, amps, mounting, feed, etc.
    """
    specs = {}
    
    # Preserve line breaks for proper pattern matching
    full_text = '\n'.join(lines)
    
    # Common patterns for panel specifications
    # Each pattern captures only the value, stopping at line breaks or common delimiters
    patterns = {
        'panel_name': re.compile(r'(?:panel\s*(?:name|id|designation)?|panelboard)\s*:?\s*([A-Z0-9\-]+)', re.IGNORECASE),
        'voltage': re.compile(r'(?:voltage|volt)\s*:?\s*(\d+(?:/\d+)?)\s*v(?:olts?)?', re.IGNORECASE),
        'phase': re.compile(r'(?:phase|phases?)\s*:?\s*(\d+)', re.IGNORECASE),
        'wire': re.compile(r'(?:wire|wires?)\s*:?\s*(\d+)', re.IGNORECASE),
        'main_bus_amps': re.compile(r'(?:main\s*bus\s*amps?|bus\s*amps?|main\s*amps?)\s*:?\s*(\d+)\s*a(?:mps?)?', re.IGNORECASE),
        'main_breaker': re.compile(r'(?:main\s*(?:circuit\s*)?breaker|mcb)\s*:?\s*([A-Z0-9\s\-/]+?)(?:\n|$)', re.IGNORECASE),
        'mounting': re.compile(r'(?:mounting|mount)\s*:?\s*([A-Z]+?)(?:\s|$|\n)', re.IGNORECASE),
        'feed': re.compile(r'(?:feed(?:\s*from)?|fed\s*from)\s*:?\s*([^\n]+?)(?:\n|$)', re.IGNORECASE),
        'location': re.compile(r'(?:location|loc)\s*:?\s*([^\n]+?)(?:\n|$)', re.IGNORECASE),
        'number_of_ckts': re.compile(r'(?:number\s*of\s*(?:circuits?|ckts?)|circuits?|ckts?)\s*:?\s*(\d+)', re.IGNORECASE),
    }
    
    for key, pattern in patterns.items():
        match = pattern.search(full_text)
        if match:
            value = match.group(1).strip()
            # Clean up excessive whitespace
            value = ' '.join(value.split())
            if value:  # Only add non-empty values
                specs[key] = value
                logger.info(f"Extracted {key}: {value}")
    
    return specs
