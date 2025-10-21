
from pathlib import Path
from typing import List, Tuple
import re
import pytesseract
from PIL import Image
import io

def ocr_image_to_lines(image_path: Path) -> List[str]:
    img = Image.open(image_path)
    # Convert to grayscale for better OCR
    img = img.convert("L")
    text = pytesseract.image_to_string(img)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return lines

CIRCUIT_RE = re.compile(r"^(?P<num>\d{1,3})(?:[A-C]?)\s*[-:.\s]?\s*(?P<desc>.+)$", re.IGNORECASE)

def parse_circuits_from_lines(lines: List[str]) -> List[Tuple[str,str]]:
    circuits = []
    for ln in lines:
        m = CIRCUIT_RE.match(ln)
        if m:
            num = m.group("num").strip()
            desc = m.group("desc").strip()
            circuits.append((num, desc))
    return circuits
