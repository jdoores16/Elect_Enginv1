"""
Visual Breaker Detection Module

Analyzes physical breaker appearance to detect:
- Handle ties (metal clips connecting breakers)
- Continuous handles (single handle spanning multiple positions)
- Multi-pole breaker groupings (2-pole, 3-pole)
- Breaker amperage ratings from handle labels

Includes AI-powered vision analysis for accurate detection.
"""

import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional
import logging
from pathlib import Path
import base64
import json

logger = logging.getLogger(__name__)


def analyze_panel_with_ai_vision(image_path: str, debug: bool = False) -> Dict:
    """
    Use OpenAI Vision API to analyze a panelboard image and detect breakers.
    
    This provides more accurate detection than traditional CV for:
    - Breaker handle sizes (1-pole, 2-pole, 3-pole)
    - Breaker amperage ratings from handle labels
    - Overall panel configuration
    
    Args:
        image_path: Path to panel image
        debug: If True, log additional debug info
        
    Returns:
        Dictionary with detected breakers and their configurations
    """
    from app.core.settings import settings
    from openai import OpenAI
    
    try:
        api_key = settings.effective_api_key
        base_url = settings.effective_base_url
    except RuntimeError:
        logger.warning("OpenAI API key not configured, skipping AI vision analysis")
        return {}
    
    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        
        with open(image_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')
        
        ext = Path(image_path).suffix.lower()
        mime_type = "image/jpeg" if ext in [".jpg", ".jpeg"] else "image/png"
        
        system_prompt = """You are an expert electrical engineer analyzing a panelboard/breaker panel photo.
Analyze the image and identify ALL circuit breakers visible in the panel.

For each breaker, determine:
1. Circuit position(s) - which circuit numbers it occupies (odd numbers on left column, even on right)
2. Pole count - 1-pole (single narrow handle), 2-pole (wider handle spanning 2 spaces), or 3-pole (spans 3 spaces)
3. Amperage rating - read the number on the breaker handle (15, 20, 30, 40, 50, 60, 70, 100, etc.)
4. Column - left (odd circuits) or right (even circuits)

Key visual indicators:
- 1-pole breakers have a single narrow handle taking one position
- 2-pole breakers have a WIDER handle (often with a tie bar) spanning 2 vertical positions
- 3-pole breakers span 3 positions with an even wider/taller handle
- Amperage is usually printed on the handle (20, 40, etc.)
- Empty/blank positions have no breaker installed

Return ONLY a valid JSON object in this exact format:
{
  "panel_info": {
    "manufacturer": "detected manufacturer name or null",
    "voltage": "detected voltage or null",
    "total_spaces": number of circuit spaces detected
  },
  "breakers": [
    {
      "circuits": [1, 3],
      "poles": 2,
      "amps": 40,
      "column": "left",
      "position_start": 1,
      "description": "2-pole 40A breaker"
    }
  ],
  "empty_spaces": [13, 14, 15, 16]
}"""

        user_prompt = """Analyze this electrical panel image. Identify every circuit breaker:
- Look at the left column (odd circuits: 1, 3, 5, 7...) and right column (even circuits: 2, 4, 6, 8...)
- For each breaker, note if it's a single pole (1P), double pole (2P), or triple pole (3P)
- Read the amperage rating printed on each breaker handle
- Note any empty/unused circuit positions

Return ONLY the JSON object with your findings."""

        vision_model = "gpt-4o"
        
        response = client.chat.completions.create(
            model=vision_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"{system_prompt}\n\n{user_prompt}"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}",
                                "detail": "high"
                            }
                        }
                    ]
                }
            ],
            max_tokens=2000,
            temperature=0.1
        )
        
        response_text = response.choices[0].message.content.strip()
        
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        result = json.loads(response_text)
        
        logger.info(f"AI Vision detected {len(result.get('breakers', []))} breakers")
        if debug:
            logger.debug(f"AI Vision result: {json.dumps(result, indent=2)}")
        
        multipole_groups = {}
        for breaker in result.get('breakers', []):
            if breaker.get('poles', 1) > 1:
                circuits = breaker.get('circuits', [])
                if circuits:
                    main_circuit = min(circuits)
                    multipole_groups[main_circuit] = {
                        'poles': breaker.get('poles'),
                        'circuits': sorted(circuits),
                        'amps': breaker.get('amps'),
                        'detection_method': 'ai_vision'
                    }
        
        return {
            'ai_vision_success': True,
            'panel_info': result.get('panel_info', {}),
            'breakers': result.get('breakers', []),
            'empty_spaces': result.get('empty_spaces', []),
            'multipole_groups': multipole_groups,
            'breaker_count': len(result.get('breakers', [])),
            'visual_detection_successful': True
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI Vision response as JSON: {e}")
        return {'ai_vision_success': False, 'error': 'Invalid JSON response'}
    except Exception as e:
        logger.error(f"AI Vision analysis failed: {e}", exc_info=True)
        return {'ai_vision_success': False, 'error': str(e)}


class BreakerRegion:
    """Represents a detected breaker region"""
    def __init__(self, x: int, y: int, w: int, h: int, circuit_num: Optional[int] = None):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.circuit_num = circuit_num
        self.amperage = None
        self.has_handle_tie = False
        self.part_of_continuous_handle = False
        
    @property
    def center(self) -> Tuple[int, int]:
        return (self.x + self.w // 2, self.y + self.h // 2)
    
    @property
    def bbox(self) -> Tuple[int, int, int, int]:
        return (self.x, self.y, self.w, self.h)


def detect_breaker_regions(image: np.ndarray, debug: bool = False) -> List[BreakerRegion]:
    """
    Detect individual breaker positions in the panel image.
    
    Args:
        image: Input image (BGR format)
        debug: If True, save debug visualization
        
    Returns:
        List of BreakerRegion objects
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Enhance contrast to make breakers stand out
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    
    # Edge detection to find breaker outlines
    edges = cv2.Canny(enhanced, 50, 150)
    
    # Morphological operations to connect edges
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    dilated = cv2.dilate(edges, kernel, iterations=2)
    
    # Find contours (potential breaker regions)
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    breaker_regions = []
    min_area = 500  # Minimum area for a breaker
    max_area = 20000  # Maximum area for a breaker
    
    for contour in contours:
        area = cv2.contourArea(contour)
        if min_area < area < max_area:
            x, y, w, h = cv2.boundingRect(contour)
            
            # Breakers are typically taller than wide (aspect ratio check)
            aspect_ratio = h / w if w > 0 else 0
            if 1.2 < aspect_ratio < 4.0:
                breaker_regions.append(BreakerRegion(x, y, w, h))
    
    # Sort by Y position (top to bottom), then X position (left to right)
    breaker_regions.sort(key=lambda b: (b.y, b.x))
    
    logger.info(f"Detected {len(breaker_regions)} potential breaker regions")
    
    if debug:
        debug_img = image.copy()
        for br in breaker_regions:
            cv2.rectangle(debug_img, (br.x, br.y), (br.x + br.w, br.y + br.h), (0, 255, 0), 2)
        cv2.imwrite('/tmp/debug_breaker_regions.jpg', debug_img)
    
    return breaker_regions


def _cluster_breakers_by_column(breaker_regions: List[BreakerRegion]) -> Dict[str, List[Tuple[int, BreakerRegion]]]:
    """
    Cluster breakers into left/right columns using K-means-like approach.
    
    Returns dictionary mapping column name to list of (index, breaker) tuples.
    """
    if not breaker_regions:
        return {}
    
    # Extract X positions
    x_positions = [br.center[0] for br in breaker_regions]
    
    # For panelboards, typically 2 columns (odd/even circuits)
    # Find the median X to split left/right
    median_x = np.median(x_positions)
    
    left_col = []
    right_col = []
    
    for idx, br in enumerate(breaker_regions):
        if br.center[0] < median_x:
            left_col.append((idx, br))
        else:
            right_col.append((idx, br))
    
    columns = {}
    if left_col:
        columns['left'] = left_col
    if right_col:
        columns['right'] = right_col
    
    logger.info(f"Clustered breakers: left={len(left_col)}, right={len(right_col)}")
    return columns


def detect_handle_ties(image: np.ndarray, breaker_regions: List[BreakerRegion], debug: bool = False) -> List[Tuple[int, int]]:
    """
    Detect handle ties (metal clips) connecting breakers.
    
    Args:
        image: Input image (BGR format)
        breaker_regions: List of detected breaker regions
        debug: If True, save debug visualization
        
    Returns:
        List of tuples indicating connected breaker indices
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    handle_ties = []
    
    # Cluster breakers by column (left/right)
    columns = _cluster_breakers_by_column(breaker_regions)
    
    # Within each column, check vertically adjacent pairs
    for col_name, breakers_in_col in columns.items():
        # Sort by Y position
        breakers_in_col.sort(key=lambda x: x[1].y)
        
        # Check consecutive pairs in this column
        for i in range(len(breakers_in_col) - 1):
            idx1, br1 = breakers_in_col[i]
            idx2, br2 = breakers_in_col[i + 1]
            
            vertical_distance = abs(br1.center[1] - br2.center[1])
            
            if 40 < vertical_distance < 150:
                # Extract region between the two breakers
                y_min = min(br1.y + br1.h, br2.y)
                y_max = max(br1.y + br1.h, br2.y)
                x_min = min(br1.x, br2.x)
                x_max = max(br1.x + br1.w, br2.x + br2.w)
                
                if y_min < y_max and x_min < x_max:
                    between_region = gray[y_min:y_max, x_min:x_max]
                    
                    # Handle ties are typically metallic and create strong vertical edges
                    edges = cv2.Canny(between_region, 100, 200)
                    vertical_lines = cv2.reduce(edges, 0, cv2.REDUCE_SUM, dtype=cv2.CV_32F)
                    
                    # If we detect significant vertical structure, it's likely a handle tie
                    if np.max(vertical_lines) > 500:
                        handle_ties.append((idx1, idx2))
                        breaker_regions[idx1].has_handle_tie = True
                        breaker_regions[idx2].has_handle_tie = True
                        logger.info(f"Detected handle tie between breakers {idx1} and {idx2}")
    
    if debug:
        debug_img = image.copy()
        for i, j in handle_ties:
            br1, br2 = breaker_regions[i], breaker_regions[j]
            cv2.line(debug_img, br1.center, br2.center, (255, 0, 0), 3)
        cv2.imwrite('/tmp/debug_handle_ties.jpg', debug_img)
    
    return handle_ties


def detect_continuous_handles(image: np.ndarray, breaker_regions: List[BreakerRegion], debug: bool = False) -> List[List[int]]:
    """
    Detect continuous handles spanning multiple breaker positions (3-pole breakers).
    
    Args:
        image: Input image (BGR format)
        breaker_regions: List of detected breaker regions
        debug: If True, save debug visualization
        
    Returns:
        List of breaker index groups (each group is a continuous handle)
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    continuous_groups = []
    
    # Cluster breakers by column (left/right)
    columns = _cluster_breakers_by_column(breaker_regions)
    
    # Within each column, look for groups of 3 consecutive breakers
    for col_name, breakers_in_col in columns.items():
        breakers_in_col.sort(key=lambda x: x[1].y)
        
        for i in range(len(breakers_in_col) - 2):
            idx1, br1 = breakers_in_col[i]
            idx2, br2 = breakers_in_col[i + 1]
            idx3, br3 = breakers_in_col[i + 2]
            
            # Extract the handle region (left portion of breakers)
            x_min = min(br1.x, br2.x, br3.x)
            x_max = max(br1.x, br2.x, br3.x) + 30  # Handle width
            y_min = br1.y
            y_max = br3.y + br3.h
            
            if x_min < x_max and y_min < y_max:
                handle_region = gray[y_min:y_max, x_min:x_max]
                
                # Detect if there's a continuous vertical structure (single handle)
                edges = cv2.Canny(handle_region, 100, 200)
                
                # Check for vertical continuity
                vertical_projection = cv2.reduce(edges, 1, cv2.REDUCE_SUM, dtype=cv2.CV_32F).flatten()
                
                # If most rows have edge content, it's a continuous handle
                non_zero_rows = np.count_nonzero(vertical_projection > 10)
                continuity_ratio = non_zero_rows / len(vertical_projection) if len(vertical_projection) > 0 else 0
                
                if continuity_ratio > 0.6:  # 60% continuity threshold
                    continuous_groups.append([idx1, idx2, idx3])
                    breaker_regions[idx1].part_of_continuous_handle = True
                    breaker_regions[idx2].part_of_continuous_handle = True
                    breaker_regions[idx3].part_of_continuous_handle = True
                    logger.info(f"Detected continuous handle spanning breakers {idx1}, {idx2}, {idx3}")
    
    if debug:
        debug_img = image.copy()
        for group in continuous_groups:
            for idx in group:
                br = breaker_regions[idx]
                cv2.rectangle(debug_img, (br.x, br.y), (br.x + br.w, br.y + br.h), (0, 0, 255), 3)
        cv2.imwrite('/tmp/debug_continuous_handles.jpg', debug_img)
    
    return continuous_groups


def assign_circuit_numbers(breaker_regions: List[BreakerRegion], image: np.ndarray) -> List[BreakerRegion]:
    """
    Assign circuit numbers to breaker regions by detecting circuit number labels.
    
    Args:
        breaker_regions: List of detected breaker regions
        image: Input image for OCR
        
    Returns:
        Updated breaker regions with circuit numbers
    """
    # Circuit numbers are typically found adjacent to breakers
    # This would use OCR on the area next to each breaker
    # For now, assign based on position (odd left column, even right column)
    
    # Sort regions into left and right columns
    if not breaker_regions:
        return breaker_regions
    
    x_positions = [br.center[0] for br in breaker_regions]
    median_x = np.median(x_positions)
    
    left_breakers = [br for br in breaker_regions if br.center[0] < median_x]
    right_breakers = [br for br in breaker_regions if br.center[0] >= median_x]
    
    left_breakers.sort(key=lambda b: b.y)
    right_breakers.sort(key=lambda b: b.y)
    
    # Assign odd numbers to left column, even to right
    for i, br in enumerate(left_breakers):
        br.circuit_num = (i * 2) + 1
    
    for i, br in enumerate(right_breakers):
        br.circuit_num = (i * 2) + 2
    
    return breaker_regions


def group_multipole_circuits(
    breaker_regions: List[BreakerRegion],
    handle_ties: List[Tuple[int, int]],
    continuous_groups: List[List[int]]
) -> Dict[int, Dict]:
    """
    Group circuits into multi-pole configurations based on visual detection.
    
    Args:
        breaker_regions: List of breaker regions with circuit numbers
        handle_ties: List of handle tie connections
        continuous_groups: List of continuous handle groups
        
    Returns:
        Dictionary mapping circuit number to multi-pole configuration
        Format: {circuit_num: {'poles': 2/3, 'circuits': [1, 3], 'detection_method': 'handle_tie'/'continuous_handle'}}
    """
    multipole_groups = {}
    
    # Process continuous handles (3-pole breakers)
    for group in continuous_groups:
        if len(group) >= 3:
            circuit_nums = [breaker_regions[i].circuit_num for i in group if breaker_regions[i].circuit_num]
            if circuit_nums:
                main_circuit = min(circuit_nums)
                multipole_groups[main_circuit] = {
                    'poles': 3,
                    'circuits': sorted(circuit_nums),
                    'detection_method': 'continuous_handle'
                }
    
    # Process handle ties (2-pole breakers)
    for i, j in handle_ties:
        # Skip if already part of a 3-pole group
        ci = breaker_regions[i].circuit_num
        cj = breaker_regions[j].circuit_num
        
        if ci and cj:
            if ci not in multipole_groups and cj not in multipole_groups:
                main_circuit = min(ci, cj)
                multipole_groups[main_circuit] = {
                    'poles': 2,
                    'circuits': sorted([ci, cj]),
                    'detection_method': 'handle_tie'
                }
    
    logger.info(f"Identified {len(multipole_groups)} multi-pole circuit groups")
    return multipole_groups


def analyze_panel_breakers(image_path: str, debug: bool = False) -> Dict:
    """
    Main entry point for visual breaker analysis.
    
    Uses AI Vision analysis first for accurate detection, with fallback to
    traditional computer vision if AI is not available.
    
    Args:
        image_path: Path to panel image
        debug: If True, save debug visualizations
        
    Returns:
        Dictionary with visual analysis results
    """
    logger.info(f"Analyzing panel breakers in image: {image_path}")
    
    # Try AI Vision analysis first (more accurate)
    logger.info("Attempting AI Vision analysis for breaker detection...")
    ai_result = analyze_panel_with_ai_vision(image_path, debug=debug)
    
    if ai_result.get('ai_vision_success'):
        logger.info(f"AI Vision analysis successful: {ai_result.get('breaker_count', 0)} breakers detected")
        return ai_result
    
    # Fallback to traditional CV analysis
    logger.info("Falling back to traditional CV analysis...")
    
    image = cv2.imread(str(image_path))
    if image is None:
        logger.error(f"Failed to load image: {image_path}")
        return {}
    
    # Step 1: Detect breaker regions
    breaker_regions = detect_breaker_regions(image, debug=debug)
    
    if not breaker_regions:
        logger.warning("No breaker regions detected with CV")
        return {'breaker_count': 0, 'multipole_groups': {}, 'visual_detection_successful': False}
    
    # Step 2: Assign circuit numbers
    breaker_regions = assign_circuit_numbers(breaker_regions, image)
    
    # Step 3: Detect handle ties
    handle_ties = detect_handle_ties(image, breaker_regions, debug=debug)
    
    # Step 4: Detect continuous handles
    continuous_groups = detect_continuous_handles(image, breaker_regions, debug=debug)
    
    # Step 5: Group multi-pole circuits
    multipole_groups = group_multipole_circuits(breaker_regions, handle_ties, continuous_groups)
    
    result = {
        'breaker_count': len(breaker_regions),
        'multipole_groups': multipole_groups,
        'visual_detection_successful': len(multipole_groups) > 0
    }
    
    logger.info(f"CV breaker analysis complete: {result}")
    return result
