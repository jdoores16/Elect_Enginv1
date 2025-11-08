"""
Visual + Text OCR Integration

Combines traditional text OCR with computer vision for:
1. Visual breaker detection (handle ties, continuous handles)
2. Visual nameplate detection (structured table extraction)
3. Smart merging of visual + text results
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

from app.skills.visual_breaker_detection import analyze_panel_breakers
from app.skills.visual_nameplate_detection import analyze_panel_nameplate
from app.skills.ocr_enhanced import extract_panel_specs_enhanced, parse_circuits_with_confidence
from app.skills.image_preprocessing import preprocess_image

logger = logging.getLogger(__name__)


def merge_visual_and_text_panel_specs(
    text_specs: Dict,
    visual_nameplate: Dict
) -> Dict:
    """
    Merge panel specs from text OCR and visual nameplate detection.
    Visual detection takes priority for structured nameplate data.
    
    Args:
        text_specs: Panel specs from text OCR
        visual_nameplate: Data from visual nameplate detection
        
    Returns:
        Merged panel specs
    """
    merged = {}
    
    # Start with text OCR results
    if text_specs:
        for key, extraction in text_specs.items():
            if extraction.value:
                merged[key] = extraction.value
    
    # Override with visual nameplate data (higher confidence for structured tables)
    if visual_nameplate.get('nameplate_detected'):
        nameplate_data = visual_nameplate.get('data', {})
        
        # Map visual nameplate fields to text OCR field names
        field_mapping = {
            'voltage': 'voltage',
            'phase': 'phase',
            'wire': 'wire',
            'main_bus_amps': 'main_bus_amps',
            'panel_type': 'panel_type',
            'neutral_amps': 'neutral_amps',
        }
        
        for visual_key, text_key in field_mapping.items():
            if visual_key in nameplate_data:
                merged[text_key] = nameplate_data[visual_key]
                logger.info(f"Visual nameplate override: {text_key} = {nameplate_data[visual_key]}")
    
    return merged


def apply_visual_multipole_detection(
    circuits: List[Dict],
    visual_breakers: Dict
) -> List[Dict]:
    """
    Apply visual multi-pole detection to circuits.
    Updates pole count based on visual handle tie and continuous handle detection.
    
    Args:
        circuits: Circuit list from text OCR
        visual_breakers: Visual breaker analysis results
        
    Returns:
        Updated circuits with visual pole detection
    """
    if not visual_breakers.get('visual_detection_successful'):
        logger.info("No visual multi-pole groups detected, using text OCR only")
        return circuits
    
    multipole_groups = visual_breakers.get('multipole_groups', {})
    
    if not multipole_groups:
        return circuits
    
    logger.info(f"Applying visual multi-pole detection: {len(multipole_groups)} groups found")
    
    # Create lookup by circuit number
    circuits_by_num = {int(c['number']): c for c in circuits if c.get('number')}
    
    # Apply visual pole detection
    for main_circuit, group_info in multipole_groups.items():
        poles = group_info['poles']
        circuit_nums = group_info['circuits']
        detection_method = group_info['detection_method']
        
        logger.info(f"Visual detection: Circuit {main_circuit} is {poles}-pole (via {detection_method})")
        
        # Update all circuits in the group
        for circuit_num in circuit_nums:
            if circuit_num in circuits_by_num:
                # If text OCR didn't detect poles or detected wrong poles, override with visual
                current_poles = circuits_by_num[circuit_num].get('breaker_poles', 'MISSING')
                
                if current_poles == 'MISSING' or current_poles != str(poles):
                    circuits_by_num[circuit_num]['breaker_poles'] = str(poles)
                    circuits_by_num[circuit_num]['visual_pole_detection'] = True
                    circuits_by_num[circuit_num]['detection_method'] = detection_method
                    logger.info(f"  - Updated circuit {circuit_num}: poles={poles} (visual override)")
    
    return circuits


def analyze_panel_image_visual_enhanced(
    image_path: str,
    enable_preprocessing: bool = True,
    debug: bool = False
) -> Dict:
    """
    Main entry point for visual-enhanced OCR analysis.
    
    Combines:
    1. Image preprocessing
    2. Text OCR extraction
    3. Visual breaker detection
    4. Visual nameplate detection
    5. Smart merging of all results
    
    Args:
        image_path: Path to panel image
        enable_preprocessing: If True, apply advanced image preprocessing
        debug: If True, save debug visualizations
        
    Returns:
        Combined analysis results with panel_specs and circuits
    """
    logger.info(f"Starting visual-enhanced OCR analysis on: {image_path}")
    
    results = {
        'success': False,
        'panel_specs': {},
        'circuits': [],
        'visual_breaker_detection': {},
        'visual_nameplate_detection': {},
        'confidence': 0.0,
        'gaps': [],
        'needs_manual_review': False,
    }
    
    try:
        # Step 1: Preprocess image for better OCR
        if enable_preprocessing:
            logger.info("Applying image preprocessing...")
            from PIL import Image
            import pytesseract
            
            preprocessed_img, _ = preprocess_image(image_path, debug=debug)
            
            # Extract text from preprocessed image
            ocr_text = pytesseract.image_to_string(preprocessed_img, config='--psm 3 --oem 3')
            ocr_lines = [line.strip() for line in ocr_text.split('\n') if line.strip()]
        else:
            # Use raw image
            import pytesseract
            ocr_text = pytesseract.image_to_string(str(image_path), config='--psm 3 --oem 3')
            ocr_lines = [line.strip() for line in ocr_text.split('\n') if line.strip()]
        
        logger.info(f"Extracted {len(ocr_lines)} lines of text from OCR")
        
        # Step 2: Text OCR extraction with confidence scoring
        logger.info("Extracting panel specs from text OCR...")
        text_ocr_result = extract_panel_specs_enhanced(ocr_lines)
        
        # Step 3: Visual nameplate detection (with fallback)
        logger.info("Running visual nameplate detection...")
        try:
            visual_nameplate = analyze_panel_nameplate(image_path, debug=debug)
        except Exception as e:
            logger.warning(f"Visual nameplate detection failed: {e}")
            visual_nameplate = {}
        
        # Step 4: Merge panel specs (visual takes priority)
        logger.info("Merging text OCR and visual nameplate data...")
        merged_specs = merge_visual_and_text_panel_specs(
            text_ocr_result.panel_specs,
            visual_nameplate
        )
        
        # Step 5: Parse circuits from text OCR
        logger.info("Parsing circuits from text OCR...")
        circuits, circuit_confidence, missing_circuits = parse_circuits_with_confidence(
            ocr_lines,
            number_of_ckts=None,
            use_ai_fallback=True
        )
        
        # Step 6: Visual breaker detection (with fallback)
        logger.info("Running visual breaker detection...")
        try:
            visual_breakers = analyze_panel_breakers(image_path, debug=debug)
        except Exception as e:
            logger.warning(f"Visual breaker detection failed: {e}")
            visual_breakers = {}
        
        # Step 7: Apply visual multi-pole detection (only if visual detection succeeded)
        if visual_breakers:
            logger.info("Applying visual multi-pole detection to circuits...")
            circuits = apply_visual_multipole_detection(circuits, visual_breakers)
        else:
            logger.info("Skipping visual multi-pole detection (no visual breaker data)")
        
        # Step 8: Compile results
        results['success'] = True
        results['panel_specs'] = merged_specs
        results['circuits'] = circuits
        results['visual_breaker_detection'] = visual_breakers
        results['visual_nameplate_detection'] = visual_nameplate
        results['confidence'] = (text_ocr_result.overall_confidence + circuit_confidence) / 2
        results['gaps'] = text_ocr_result.gaps + [f"circuit_{i}" for i in missing_circuits]
        results['needs_manual_review'] = text_ocr_result.needs_manual_review or circuit_confidence < 0.6
        
        logger.info(f"Visual-enhanced OCR complete. Confidence: {results['confidence']:.2f}")
        logger.info(f"  - Panel specs: {len(merged_specs)} fields")
        logger.info(f"  - Circuits: {len(circuits)} found")
        logger.info(f"  - Visual breakers: {visual_breakers.get('breaker_count', 0)} detected")
        logger.info(f"  - Visual nameplate: {'detected' if visual_nameplate.get('nameplate_detected') else 'not detected'}")
        
    except Exception as e:
        logger.error(f"Visual-enhanced OCR failed: {e}", exc_info=True)
        results['error'] = str(e)
    
    return results
