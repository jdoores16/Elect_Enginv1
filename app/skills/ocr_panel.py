
from pathlib import Path
from typing import List, Tuple
import re
import logging
import pytesseract
from PIL import Image
import io

logger = logging.getLogger(__name__)

def ocr_image_to_lines(image_path: Path) -> List[str]:
    try:
        img = Image.open(image_path)
        # Convert to grayscale for better OCR
        img = img.convert("L")
        text = pytesseract.image_to_string(img)
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        logger.info(f"OCR extracted {len(lines)} lines from {image_path.name}")
        return lines
    except pytesseract.TesseractNotFoundError as e:
        logger.error(f"Tesseract OCR is not installed or not in PATH. Please install Tesseract. Error: {e}")
        raise
    except Exception as e:
        logger.error(f"Error during OCR processing of {image_path}: {e.__class__.__name__}: {e}")
        raise

CIRCUIT_RE = re.compile(r"^(?P<num>\d{1,3})(?:[A-C]?)\s*[-:.\s]?\s*(?P<desc>.+)$", re.IGNORECASE)

def parse_circuits_from_lines(lines: List[str]) -> List[Tuple[str,str]]:
    circuits = []
    skipped = 0
    for ln in lines:
        m = CIRCUIT_RE.match(ln)
        if m:
            num = m.group("num").strip()
            desc = m.group("desc").strip()
            circuits.append((num, desc))
        else:
            skipped += 1
    
    logger.info(f"Parsed {len(circuits)} circuits from {len(lines)} OCR lines. Skipped {skipped} non-matching lines.")
    if skipped > len(lines) * 0.8:
        logger.warning(f"High skip rate ({skipped}/{len(lines)}). OCR quality may be poor or circuit format doesn't match expected pattern.")
    
    return circuits

def extract_panel_specs(lines: List[str]) -> dict:
    """
    Extract panel specifications from OCR text lines.
    Looks for voltage, phase, wire, amps, mounting, feed, etc.
    """
    specs = {}
    
    # Preserve line breaks for proper pattern matching
    full_text = '\n'.join(lines)
    
    # Common patterns for panel specifications
    # Each pattern captures only the value, stopping at line breaks or common delimiters
    patterns = {
        'voltage': re.compile(r'(?:voltage|volt)\s*:?\s*(\d+(?:/\d+)?)\s*v(?:olts?)?', re.IGNORECASE),
        'phase': re.compile(r'(?:phase|phases?)\s*:?\s*(\d+)', re.IGNORECASE),
        'wire': re.compile(r'(?:wire|wires?)\s*:?\s*(\d+)', re.IGNORECASE),
        'main_bus_amps': re.compile(r'(?:main\s*bus\s*amps?|bus\s*amps?|main\s*amps?)\s*:?\s*(\d+)\s*a(?:mps?)?', re.IGNORECASE),
        'main_breaker': re.compile(r'(?:main\s*(?:circuit\s*)?breaker|mcb)\s*:?\s*([A-Z0-9\s\-/]+?)(?:\n|$)', re.IGNORECASE),
        'mounting': re.compile(r'(?:mounting|mount)\s*:?\s*([A-Z]+?)(?:\s|$|\n)', re.IGNORECASE),
        'feed': re.compile(r'(?:feed(?:\s*from)?|fed\s*from)\s*:?\s*([^\n]+?)(?:\n|$)', re.IGNORECASE),
        'location': re.compile(r'(?:location|loc)\s*:?\s*([^\n]+?)(?:\n|$)', re.IGNORECASE),
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
