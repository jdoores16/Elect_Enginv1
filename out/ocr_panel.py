
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
