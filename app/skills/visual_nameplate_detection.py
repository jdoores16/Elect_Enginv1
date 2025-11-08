"""
Visual Nameplate Detection Module

Detects and extracts structured nameplate information from panel images.
Targets table-like structures with key-value pairs:
- Voltage
- Phase
- Wire
- Panel Amps (Main Bus Amps)
- Neutral Amps
- Panel Type
- etc.
"""

import cv2
import numpy as np
import pytesseract
from typing import Dict, List, Tuple, Optional
import logging
import re

logger = logging.getLogger(__name__)


def detect_table_regions(image: np.ndarray, debug: bool = False) -> List[Tuple[int, int, int, int]]:
    """
    Detect rectangular table regions in the image (potential nameplates).
    
    Args:
        image: Input image (BGR format)
        debug: If True, save debug visualizations
        
    Returns:
        List of bounding boxes (x, y, w, h) for detected tables
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Enhance contrast
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    
    # Detect edges (tables have strong rectangular borders)
    edges = cv2.Canny(enhanced, 50, 150)
    
    # Dilate to connect table borders
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    dilated = cv2.dilate(edges, kernel, iterations=2)
    
    # Find contours
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    table_regions = []
    min_area = 5000  # Tables are relatively large
    
    for contour in contours:
        area = cv2.contourArea(contour)
        if area > min_area:
            x, y, w, h = cv2.boundingRect(contour)
            
            # Tables are typically wider than tall
            aspect_ratio = w / h if h > 0 else 0
            if 1.2 < aspect_ratio < 4.0:
                table_regions.append((x, y, w, h))
    
    # Sort by area (largest first - likely the main nameplate)
    table_regions.sort(key=lambda t: t[2] * t[3], reverse=True)
    
    logger.info(f"Detected {len(table_regions)} potential table regions")
    
    if debug and table_regions:
        debug_img = image.copy()
        for x, y, w, h in table_regions:
            cv2.rectangle(debug_img, (x, y), (x + w, y + h), (0, 255, 0), 3)
        cv2.imwrite('/tmp/debug_table_regions.jpg', debug_img)
    
    return table_regions


def detect_table_lines(table_region: np.ndarray, debug: bool = False) -> Tuple[List[int], List[int]]:
    """
    Detect horizontal and vertical lines in a table region.
    
    Args:
        table_region: Cropped table region (grayscale)
        debug: If True, save debug visualizations
        
    Returns:
        Tuple of (horizontal_lines_y, vertical_lines_x)
    """
    # Detect horizontal lines
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
    horizontal_lines = cv2.morphologyEx(table_region, cv2.MORPH_OPEN, horizontal_kernel)
    
    # Detect vertical lines
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
    vertical_lines = cv2.morphologyEx(table_region, cv2.MORPH_OPEN, vertical_kernel)
    
    # Find y-coordinates of horizontal lines
    h_projection = cv2.reduce(horizontal_lines, 1, cv2.REDUCE_SUM, dtype=cv2.CV_32F).flatten()
    h_lines_y = [i for i, val in enumerate(h_projection) if val > 1000]
    
    # Find x-coordinates of vertical lines
    v_projection = cv2.reduce(vertical_lines, 0, cv2.REDUCE_SUM, dtype=cv2.CV_32F).flatten()
    v_lines_x = [i for i, val in enumerate(v_projection) if val > 1000]
    
    # Merge nearby lines
    h_lines_y = _merge_nearby_values(h_lines_y, threshold=10)
    v_lines_x = _merge_nearby_values(v_lines_x, threshold=10)
    
    logger.info(f"Detected {len(h_lines_y)} horizontal and {len(v_lines_x)} vertical lines")
    
    return h_lines_y, v_lines_x


def _merge_nearby_values(values: List[int], threshold: int = 10) -> List[int]:
    """Merge values that are within threshold distance."""
    if not values:
        return []
    
    values = sorted(values)
    merged = [values[0]]
    
    for val in values[1:]:
        if val - merged[-1] > threshold:
            merged.append(val)
        else:
            # Average with previous value
            merged[-1] = (merged[-1] + val) // 2
    
    return merged


def extract_table_cells(
    image: np.ndarray,
    table_bbox: Tuple[int, int, int, int],
    debug: bool = False
) -> List[Dict[str, any]]:
    """
    Extract individual cells from a table region.
    
    Args:
        image: Full image (BGR format)
        table_bbox: Bounding box of table (x, y, w, h)
        debug: If True, save debug visualizations
        
    Returns:
        List of cell dictionaries with 'bbox', 'row', 'col', 'text'
    """
    x, y, w, h = table_bbox
    table_region = image[y:y+h, x:x+w]
    gray_table = cv2.cvtColor(table_region, cv2.COLOR_BGR2GRAY)
    
    # Detect table lines
    h_lines, v_lines = detect_table_lines(gray_table, debug=debug)
    
    if len(h_lines) < 2 or len(v_lines) < 2:
        logger.warning("Insufficient table structure detected")
        return []
    
    cells = []
    
    # Extract cells based on grid
    for row_idx in range(len(h_lines) - 1):
        y1 = h_lines[row_idx]
        y2 = h_lines[row_idx + 1]
        
        for col_idx in range(len(v_lines) - 1):
            x1 = v_lines[col_idx]
            x2 = v_lines[col_idx + 1]
            
            # Extract cell region
            cell_img = gray_table[y1:y2, x1:x2]
            
            if cell_img.size == 0:
                continue
            
            # Preprocess cell for OCR
            cell_img = cv2.GaussianBlur(cell_img, (3, 3), 0)
            _, cell_img = cv2.threshold(cell_img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # OCR the cell
            cell_text = pytesseract.image_to_string(
                cell_img,
                config='--psm 7 --oem 3'  # Single line mode
            ).strip()
            
            cells.append({
                'bbox': (x + x1, y + y1, x2 - x1, y2 - y1),
                'row': row_idx,
                'col': col_idx,
                'text': cell_text
            })
    
    logger.info(f"Extracted {len(cells)} cells from table")
    
    if debug and cells:
        debug_img = table_region.copy()
        for cell in cells:
            cx, cy, cw, ch = cell['bbox']
            cx -= x
            cy -= y
            cv2.rectangle(debug_img, (cx, cy), (cx + cw, cy + ch), (255, 0, 0), 1)
        cv2.imwrite('/tmp/debug_table_cells.jpg', debug_img)
    
    return cells


def parse_nameplate_data(cells: List[Dict]) -> Dict[str, str]:
    """
    Parse nameplate key-value pairs from table cells.
    
    Args:
        cells: List of cell dictionaries
        
    Returns:
        Dictionary of extracted nameplate parameters
    """
    nameplate_data = {}
    
    # Expected nameplate fields
    field_patterns = {
        'voltage': r'volt(?:s|age)?',
        'phase': r'phase',
        'wire': r'wire',
        'panel_amps': r'(?:pnl\.?|panel)\s*amps?',
        'main_bus_amps': r'(?:main\s*bus|bus)\s*amps?',
        'neutral_amps': r'neut(?:\.|ral)?\s*amps?',
        'neutral_volts': r'neut(?:\.|ral)?\s*volt(?:s|age)?',
        'panel_type': r'(?:pnl\.?|panel)\s*type',
        'box_type': r'box\s*type',
        'mfg': r'mfg\.?\s*(?:at)?',
        'date': r'date',
        'job_no': r'job\s*no\.?',
        'neutral_cat': r'neut(?:\.|ral)?\s*cat\.?',
    }
    
    # Group cells by row
    rows = {}
    for cell in cells:
        row_idx = cell['row']
        if row_idx not in rows:
            rows[row_idx] = []
        rows[row_idx].append(cell)
    
    # Parse each row for key-value pairs
    for row_idx, row_cells in rows.items():
        row_cells.sort(key=lambda c: c['col'])
        
        # Assume left column is key, right column is value
        if len(row_cells) >= 2:
            key_cell = row_cells[0]
            value_cell = row_cells[-1]  # Last cell in row
            
            key_text = key_cell['text'].strip().lower()
            value_text = value_cell['text'].strip()
            
            # Match against known fields
            for field_name, pattern in field_patterns.items():
                if re.search(pattern, key_text, re.IGNORECASE):
                    nameplate_data[field_name] = value_text
                    logger.info(f"Extracted {field_name}: {value_text}")
                    break
    
    return nameplate_data


def clean_nameplate_values(data: Dict[str, str]) -> Dict[str, any]:
    """
    Clean and normalize nameplate values.
    
    Args:
        data: Raw nameplate data
        
    Returns:
        Cleaned and typed nameplate data
    """
    cleaned = {}
    
    # Voltage
    if 'voltage' in data:
        voltage_match = re.search(r'(\d+)', data['voltage'])
        if voltage_match:
            cleaned['voltage'] = int(voltage_match.group(1))
    
    # Phase
    if 'phase' in data:
        phase_match = re.search(r'(\d+)', data['phase'])
        if phase_match:
            cleaned['phase'] = int(phase_match.group(1))
    
    # Wire
    if 'wire' in data:
        wire_match = re.search(r'(\d+)', data['wire'])
        if wire_match:
            cleaned['wire'] = int(wire_match.group(1))
    
    # Amps (try panel_amps first, then main_bus_amps)
    amps_value = data.get('panel_amps') or data.get('main_bus_amps')
    if amps_value:
        amps_match = re.search(r'(\d+)', amps_value)
        if amps_match:
            cleaned['main_bus_amps'] = int(amps_match.group(1))
    
    # Neutral Amps
    if 'neutral_amps' in data:
        neut_amps_match = re.search(r'(\d+)', data['neutral_amps'])
        if neut_amps_match:
            cleaned['neutral_amps'] = int(neut_amps_match.group(1))
    
    # Panel Type (keep as string)
    if 'panel_type' in data:
        cleaned['panel_type'] = data['panel_type'].strip()
    
    # Date (keep as string)
    if 'date' in data:
        cleaned['date'] = data['date'].strip()
    
    logger.info(f"Cleaned nameplate data: {cleaned}")
    return cleaned


def analyze_panel_nameplate(image_path: str, debug: bool = False) -> Dict:
    """
    Main entry point for visual nameplate detection.
    
    Args:
        image_path: Path to panel image
        debug: If True, save debug visualizations
        
    Returns:
        Dictionary with extracted nameplate data
    """
    image = cv2.imread(str(image_path))
    if image is None:
        logger.error(f"Failed to load image: {image_path}")
        return {}
    
    logger.info(f"Analyzing panel nameplate in image: {image_path}")
    
    # Step 1: Detect table regions
    table_regions = detect_table_regions(image, debug=debug)
    
    if not table_regions:
        logger.warning("No table regions detected")
        return {}
    
    # Step 2: Extract cells from the largest table (likely the nameplate)
    largest_table = table_regions[0]
    cells = extract_table_cells(image, largest_table, debug=debug)
    
    if not cells:
        logger.warning("No cells extracted from table")
        return {}
    
    # Step 3: Parse nameplate data
    raw_data = parse_nameplate_data(cells)
    
    # Step 4: Clean and normalize
    cleaned_data = clean_nameplate_values(raw_data)
    
    result = {
        'nameplate_detected': len(cleaned_data) > 0,
        'data': cleaned_data,
        'raw_data': raw_data
    }
    
    logger.info(f"Visual nameplate analysis complete: {result}")
    return result
