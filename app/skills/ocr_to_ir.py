"""
OCR-to-IR Converter: Transforms OCR extraction results into validated PanelScheduleIR.
This makes OCR "just another producer" of the canonical IR format.
"""

from typing import List, Dict, Optional, Tuple
from pathlib import Path
import logging

from app.schemas.panel_ir import PanelScheduleIR, HeaderBlock, CircuitRecord, NameValuePair, LEFT_LABELS, RIGHT_LABELS
from app.skills.ocr_enhanced import OCRExtractionResult, extract_panel_specs_enhanced, parse_circuits_with_confidence
from app.skills.ocr_panel import ocr_image_to_lines

logger = logging.getLogger(__name__)


def ocr_to_ir(
    image_paths: List[Path],
    panel_name_override: Optional[str] = None,
    number_of_ckts: Optional[int] = None
) -> Tuple[PanelScheduleIR, OCRExtractionResult]:
    """
    Convert OCR extraction from images to validated PanelScheduleIR.
    
    Args:
        image_paths: List of image files to process
        panel_name_override: Optional override for panel name
        number_of_ckts: Optional circuit count override
    
    Returns:
        (PanelScheduleIR, OCRExtractionResult) - validated IR and extraction metadata
    
    Raises:
        ValidationError if IR validation fails
    """
    
    # Step 1: OCR all images
    all_lines = []
    for img_path in image_paths:
        lines = ocr_image_to_lines(img_path)
        all_lines.extend(lines)
    
    logger.info(f"OCR extracted {len(all_lines)} total lines from {len(image_paths)} images")
    
    # Step 2: Enhanced extraction with confidence
    extraction = extract_panel_specs_enhanced(all_lines)
    
    # Step 3: Parse circuits with confidence
    circuits_data, circuit_conf, missing_ckts = parse_circuits_with_confidence(all_lines, number_of_ckts)
    extraction.circuits = circuits_data
    
    logger.info(f"Circuit confidence: {circuit_conf:.2f}, Missing circuits: {len(missing_ckts)}")
    
    # Step 4: Build HeaderBlock from OCR extraction
    header = _build_header_from_extraction(extraction, panel_name_override)
    
    # Step 5: Build CircuitRecords from OCR circuits
    circuit_records = _build_circuits_from_extraction(circuits_data)
    
    # Step 6: Create and validate IR
    ir = PanelScheduleIR(
        header=header,
        circuits=circuit_records
    )
    
    logger.info(f"Successfully created PanelScheduleIR with {len(circuit_records)} circuits")
    
    return ir, extraction


def _build_header_from_extraction(extraction: OCRExtractionResult, panel_name_override: Optional[str] = None) -> HeaderBlock:
    """Build HeaderBlock from OCR extraction with proper defaults"""
    
    specs = extraction.panel_specs
    
    # Panel name: use override, or OCR, or default
    panel_name = panel_name_override or specs.get('panel_name', {}).get('value') or "PANEL00000"
    
    # Build left params with OCR values or defaults
    left_params = []
    left_defaults = {
        "VOLTAGE": "480Y/277V",
        "PHASE": "3PH",
        "WIRE": "4W+G",
        "MAIN BUS AMPS": "800",
        "MAIN CIRCUIT BREAKER": "MLO",
        "MOUNTING": "SURFACE",
        "FEED": "UPSTREAM",
        "FEED-THRU LUGS": "NO"
    }
    
    for name_cell, val_cell, text in LEFT_LABELS:
        # Map OCR field name to IR field name
        ocr_key = text.lower().replace(' ', '_').replace('-', '_')
        value = specs.get(ocr_key, {}).get('value') or left_defaults.get(text, "")
        
        left_params.append(NameValuePair(
            name_cell=name_cell,
            value_cell=val_cell,
            name_text=text,
            value=value
        ))
    
    # Build right params with OCR values or defaults
    right_params = []
    right_defaults = {
        "LOCATION": "ELECTRICAL ROOM",
        "FED FROM": "UPSTREAM",
        "UL LISTED EQUIPMENT SHORT CIRCUIT RATING": "22kA",
        "MAXIMUM AVAILABLE SHORT CIRCUIT CURRENT": "18kA",
        "PHASE CONDUCTOR": "#1/0 CU",
        "NEUTRAL CONDUCTOR": "#1/0 CU",
        "GROUND CONDUCTOR": "#6 CU"
    }
    
    for name_cell, val_cell, text in RIGHT_LABELS:
        # Map OCR field name to IR field name
        ocr_key = text.lower().replace(' ', '_').replace('-', '_')
        value = specs.get(ocr_key, {}).get('value') or right_defaults.get(text, "")
        
        right_params.append(NameValuePair(
            name_cell=name_cell,
            value_cell=val_cell,
            name_text=text,
            value=value
        ))
    
    return HeaderBlock(
        panel_name=panel_name,
        left_params=left_params,
        right_params=right_params
    )


def _build_circuits_from_extraction(circuits_data: List[Dict]) -> List[CircuitRecord]:
    """Build CircuitRecords from OCR circuit data"""
    
    circuit_records = []
    
    for ckt_data in circuits_data:
        ckt_num = int(ckt_data['number'])
        
        # Skip if completely missing
        if ckt_data.get('description') == 'MISSING' and ckt_data.get('breaker_amps') == 'MISSING':
            continue
        
        # Determine side and row
        side = "odd" if ckt_num % 2 == 1 else "even"
        excel_row = 11 + ((ckt_num + 1) // 2)
        
        # Parse breaker_amps (ensure it's valid)
        try:
            breaker_amps = float(ckt_data.get('breaker_amps', 20))
            if breaker_amps <= 0:
                breaker_amps = 20.0
        except (ValueError, TypeError):
            breaker_amps = 20.0
        
        # Parse load_amps from load field (kVA or W)
        load_amps = 0.0
        load_str = ckt_data.get('load', '0')
        if load_str != 'MISSING':
            try:
                # Extract numeric value from load string
                import re
                match = re.search(r'([\d.]+)', str(load_str))
                if match:
                    load_amps = float(match.group(1))
            except (ValueError, TypeError):
                pass
        
        # Ensure breaker and load differ
        if abs(breaker_amps - load_amps) < 0.1:
            load_amps = breaker_amps * 0.75  # 75% rule as default
        
        # Parse poles
        try:
            poles = int(ckt_data.get('breaker_poles', 1))
            if poles not in [1, 2, 3]:
                poles = 1
        except (ValueError, TypeError):
            poles = 1
        
        # Determine phases based on circuit number
        phA = ckt_num <= 2
        phB = 3 <= ckt_num <= 4
        phC = ckt_num >= 5
        
        # Description
        desc = ckt_data.get('description', '').strip().upper()
        if desc == 'MISSING' or not desc:
            desc = f"CIRCUIT {ckt_num}"
        
        circuit_records.append(CircuitRecord(
            ckt=ckt_num,
            side=side,
            excel_row=excel_row,
            breaker_amps=breaker_amps,
            load_amps=load_amps,
            poles=poles,
            phA=phA,
            phB=phB,
            phC=phC,
            description=desc
        ))
    
    return circuit_records


def manual_edits_to_ir(edited_data: Dict) -> PanelScheduleIR:
    """
    Convert manually edited OCR data to PanelScheduleIR.
    This handles the output from the manual edit form.
    """
    
    # Build header from edited specs
    specs = edited_data.get('panel_specs', {})
    
    panel_name = specs.get('panel_name', 'PANEL00000')
    
    # Build left params
    left_params = []
    for name_cell, val_cell, text in LEFT_LABELS:
        ocr_key = text.lower().replace(' ', '_').replace('-', '_')
        value = specs.get(ocr_key, '')
        
        left_params.append(NameValuePair(
            name_cell=name_cell,
            value_cell=val_cell,
            name_text=text,
            value=value if value else None
        ))
    
    # Build right params
    right_params = []
    for name_cell, val_cell, text in RIGHT_LABELS:
        ocr_key = text.lower().replace(' ', '_').replace('-', '_')
        value = specs.get(ocr_key, '')
        
        right_params.append(NameValuePair(
            name_cell=name_cell,
            value_cell=val_cell,
            name_text=text,
            value=value if value else None
        ))
    
    header = HeaderBlock(
        panel_name=panel_name,
        left_params=left_params,
        right_params=right_params
    )
    
    # Build circuits from edited data
    circuits = []
    for ckt_data in edited_data.get('circuits', []):
        ckt_num = int(ckt_data['number'])
        
        # Skip if no description
        if not ckt_data.get('description'):
            continue
        
        side = "odd" if ckt_num % 2 == 1 else "even"
        excel_row = 11 + ((ckt_num + 1) // 2)
        
        try:
            breaker_amps = float(ckt_data.get('breaker_amps', 20))
        except (ValueError, TypeError):
            breaker_amps = 20.0
        
        # Calculate load_amps from load field
        load_amps = 0.0
        load_str = ckt_data.get('load', '0')
        try:
            import re
            match = re.search(r'([\d.]+)', str(load_str))
            if match:
                load_amps = float(match.group(1))
        except (ValueError, TypeError):
            pass
        
        if abs(breaker_amps - load_amps) < 0.1:
            load_amps = breaker_amps * 0.75
        
        try:
            poles = int(ckt_data.get('breaker_poles', 1))
        except (ValueError, TypeError):
            poles = 1
        
        circuits.append(CircuitRecord(
            ckt=ckt_num,
            side=side,
            excel_row=excel_row,
            breaker_amps=breaker_amps,
            load_amps=load_amps,
            poles=poles,
            phA=ckt_num <= 2,
            phB=3 <= ckt_num <= 4,
            phC=ckt_num >= 5,
            description=ckt_data.get('description', '').strip().upper()
        ))
    
    return PanelScheduleIR(
        header=header,
        circuits=circuits
    )
