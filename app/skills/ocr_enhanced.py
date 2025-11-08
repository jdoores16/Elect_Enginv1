"""
Enhanced OCR parser with confidence scoring, gap detection, and fuzzy field matching.
Guarantees users can "fix & proceed" by surfacing low-confidence fields for manual editing.
"""

from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum
import re
import logging
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class ConfidenceLevel(str, Enum):
    """Confidence levels for OCR extractions"""
    HIGH = "high"       # >0.8
    MEDIUM = "medium"   # 0.5-0.8
    LOW = "low"         # 0.2-0.5
    MISSING = "missing" # <0.2 or not found


@dataclass
class FieldExtraction:
    """Result of extracting a single field from OCR"""
    field_name: str
    value: Optional[str] = None
    confidence: float = 0.0
    confidence_level: ConfidenceLevel = ConfidenceLevel.MISSING
    source_line: Optional[str] = None
    match_score: float = 0.0
    
    def to_dict(self) -> dict:
        return {
            "field_name": self.field_name,
            "value": self.value,
            "confidence": round(self.confidence, 2),
            "confidence_level": self.confidence_level.value,
            "source_line": self.source_line,
            "needs_review": self.confidence_level in (ConfidenceLevel.LOW, ConfidenceLevel.MISSING)
        }


@dataclass
class OCRExtractionResult:
    """Complete OCR extraction result with confidence reporting"""
    panel_specs: Dict[str, FieldExtraction] = field(default_factory=dict)
    circuits: List[Dict] = field(default_factory=list)
    overall_confidence: float = 0.0
    gaps: List[str] = field(default_factory=list)
    needs_manual_review: bool = False
    
    def to_dict(self) -> dict:
        return {
            "panel_specs": {k: v.to_dict() for k, v in self.panel_specs.items()},
            "circuits": self.circuits,
            "overall_confidence": round(self.overall_confidence, 2),
            "gaps": self.gaps,
            "needs_manual_review": self.needs_manual_review,
            "stats": {
                "total_fields": len(self.panel_specs),
                "high_confidence": sum(1 for v in self.panel_specs.values() if v.confidence_level == ConfidenceLevel.HIGH),
                "medium_confidence": sum(1 for v in self.panel_specs.values() if v.confidence_level == ConfidenceLevel.MEDIUM),
                "low_confidence": sum(1 for v in self.panel_specs.values() if v.confidence_level == ConfidenceLevel.LOW),
                "missing": sum(1 for v in self.panel_specs.values() if v.confidence_level == ConfidenceLevel.MISSING),
            }
        }


def fuzzy_match_score(text: str, pattern: str) -> float:
    """
    Calculate fuzzy match score between text and pattern using SequenceMatcher.
    Returns score between 0 and 1.
    """
    return SequenceMatcher(None, text.upper(), pattern.upper()).ratio()


def find_fuzzy_field(lines: List[str], field_variants: List[str], threshold: float = 0.7) -> Tuple[Optional[str], float, Optional[str]]:
    """
    Find field in OCR lines using fuzzy matching against multiple variants.
    Returns: (value, confidence_score, source_line)
    """
    best_match = None
    best_score = 0.0
    best_line = None
    
    for line in lines:
        line_upper = line.upper()
        for variant in field_variants:
            variant_upper = variant.upper()
            
            # Check if variant is in line
            if variant_upper in line_upper:
                # Extract value after the field name
                parts = line.split(':', 1)
                if len(parts) == 2:
                    value = parts[1].strip()
                    score = 1.0  # Perfect match
                    if score > best_score:
                        best_match = value
                        best_score = score
                        best_line = line
                else:
                    # Try to extract value after variant
                    idx = line_upper.index(variant_upper)
                    after_variant = line[idx + len(variant):].strip()
                    # Remove common separators
                    after_variant = after_variant.lstrip(':=- \t')
                    if after_variant:
                        value = after_variant.split()[0] if after_variant.split() else after_variant
                        score = 0.9  # High but not perfect
                        if score > best_score:
                            best_match = value
                            best_score = score
                            best_line = line
            else:
                # Fuzzy match
                score = fuzzy_match_score(line_upper, variant_upper)
                if score >= threshold:
                    # Try to extract value
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        value = parts[1].strip()
                        if score > best_score:
                            best_match = value
                            best_score = score
                            best_line = line
    
    return best_match, best_score, best_line


def extract_with_confidence(lines: List[str], pattern: re.Pattern, field_variants: List[str]) -> FieldExtraction:
    """
    Extract field using regex pattern first, then fuzzy matching as fallback.
    Returns FieldExtraction with confidence scoring.
    """
    full_text = '\n'.join(lines)
    
    # Try regex pattern first (highest confidence)
    match = pattern.search(full_text)
    if match:
        value = match.group(1).strip()
        value = ' '.join(value.split())  # Clean whitespace
        
        if value:
            # Find which line it came from
            source_line = None
            for line in lines:
                if value in line:
                    source_line = line
                    break
            
            return FieldExtraction(
                field_name=field_variants[0],
                value=value,
                confidence=0.95,
                confidence_level=ConfidenceLevel.HIGH,
                source_line=source_line,
                match_score=1.0
            )
    
    # Fallback to fuzzy matching
    value, score, source_line = find_fuzzy_field(lines, field_variants, threshold=0.7)
    
    if value and score > 0:
        # Determine confidence level from score
        if score >= 0.8:
            level = ConfidenceLevel.HIGH
        elif score >= 0.5:
            level = ConfidenceLevel.MEDIUM
        else:
            level = ConfidenceLevel.LOW
        
        return FieldExtraction(
            field_name=field_variants[0],
            value=value,
            confidence=score,
            confidence_level=level,
            source_line=source_line,
            match_score=score
        )
    
    # Nothing found
    return FieldExtraction(
        field_name=field_variants[0],
        confidence=0.0,
        confidence_level=ConfidenceLevel.MISSING
    )


def extract_panel_specs_enhanced(lines: List[str]) -> OCRExtractionResult:
    """
    Enhanced extraction with confidence scoring and gap detection.
    """
    result = OCRExtractionResult()
    
    # Define patterns and variants for each field
    field_configs = {
        'panel_name': {
            'pattern': re.compile(r'(?:panel\s*(?:name|id|designation)?|panelboard)\s*:?\s*([A-Z0-9\-]+)', re.IGNORECASE),
            'variants': ['PANEL NAME', 'PANEL', 'PANELBOARD', 'PANEL ID']
        },
        'voltage': {
            'pattern': re.compile(r'(?:voltage|volt)\s*:?\s*(\d+(?:[/Y]\d+)?)\s*v?(?:olts?)?', re.IGNORECASE),
            'variants': ['VOLTAGE', 'VOLT', 'V']
        },
        'phase': {
            'pattern': re.compile(r'(?:phase|phases?)\s*:?\s*([13])\s*(?:PH|Ø)?', re.IGNORECASE),
            'variants': ['PHASE', 'PH', 'PHASES']
        },
        'wire': {
            'pattern': re.compile(r'(?:wire|wires?)\s*:?\s*(\d+\s*W?(?:\+G)?)', re.IGNORECASE),
            'variants': ['WIRE', 'WIRES', 'W']
        },
        'main_bus_amps': {
            'pattern': re.compile(r'(?:main\s*bus\s*amps?|bus\s*amps?|main\s*amps?)\s*:?\s*(\d+)\s*a?(?:mps?)?', re.IGNORECASE),
            'variants': ['MAIN BUS AMPS', 'BUS AMPS', 'MAIN AMPS', 'BUS RATING']
        },
        'main_breaker': {
            'pattern': re.compile(r'(?:main\s*(?:circuit\s*)?breaker|mcb)\s*:?\s*([A-Z0-9\s\-/]+?)(?:\n|$)', re.IGNORECASE),
            'variants': ['MAIN CIRCUIT BREAKER', 'MAIN BREAKER', 'MCB']
        },
        'mounting': {
            'pattern': re.compile(r'(?:mounting|mount)\s*:?\s*([A-Z]+?)(?:\s|$|\n)', re.IGNORECASE),
            'variants': ['MOUNTING', 'MOUNT']
        },
        'feed': {
            'pattern': re.compile(r'(?:feed(?:\s*from)?|fed\s*from)\s*:?\s*([^\n]+?)(?:\n|$)', re.IGNORECASE),
            'variants': ['FEED FROM', 'FEED', 'FED FROM']
        },
        'location': {
            'pattern': re.compile(r'(?:location|loc)\s*:?\s*([^\n]+?)(?:\n|$)', re.IGNORECASE),
            'variants': ['LOCATION', 'LOC']
        },
    }
    
    # Extract each field with confidence
    for field_key, config in field_configs.items():
        extraction = extract_with_confidence(lines, config['pattern'], config['variants'])
        extraction.field_name = field_key
        result.panel_specs[field_key] = extraction
    
    # Calculate overall confidence
    confidences = [e.confidence for e in result.panel_specs.values()]
    result.overall_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    
    # Detect gaps (missing or low confidence fields)
    for field_key, extraction in result.panel_specs.items():
        if extraction.confidence_level in (ConfidenceLevel.MISSING, ConfidenceLevel.LOW):
            result.gaps.append(field_key)
    
    # Determine if manual review is needed
    result.needs_manual_review = (
        result.overall_confidence < 0.7 or
        len(result.gaps) > 3 or
        any(e.confidence_level == ConfidenceLevel.MISSING for e in result.panel_specs.values() if e.field_name in ['panel_name', 'voltage'])
    )
    
    return result


def parse_circuits_with_confidence(lines: List[str], number_of_ckts: int = None, use_ai_fallback: bool = True) -> Tuple[List[Dict], float, List[int]]:
    """
    Parse circuits with confidence scoring.
    Uses AI extraction as fallback when regex confidence is low.
    
    Args:
        lines: OCR text lines
        number_of_ckts: Number of circuits (optional)
        use_ai_fallback: If True, use AI to enhance low-confidence extractions
        
    Returns: (circuits, average_confidence, gap_circuit_numbers)
    """
    from app.skills.ocr_panel import parse_circuits_from_lines, CIRCUIT_RE
    
    circuits = parse_circuits_from_lines(lines, number_of_ckts)
    
    found_count = 0
    missing_circuits = []
    
    for i, circuit in enumerate(circuits, start=1):
        if circuit.get('description') != 'MISSING':
            found_count += 1
            missing_fields = sum(1 for v in circuit.values() if v == 'MISSING')
            circuit['confidence'] = 1.0 - (missing_fields / len(circuit))
        else:
            circuit['confidence'] = 0.0
            missing_circuits.append(i)
    
    avg_confidence = found_count / len(circuits) if circuits else 0.0
    
    if use_ai_fallback and avg_confidence < 0.6:
        logger.info(f"Regex confidence ({avg_confidence:.2f}) is low, attempting AI enhancement")
        try:
            from app.skills.ai_ocr_extraction import ai_extract_circuits, merge_regex_and_ai_results
            
            ai_circuits = ai_extract_circuits(lines)
            
            if ai_circuits:
                circuits = merge_regex_and_ai_results(circuits, ai_circuits)
                
                found_count = sum(1 for c in circuits if c.get('description') != 'MISSING')
                avg_confidence = found_count / len(circuits) if circuits else 0.0
                
                missing_circuits = [i for i, c in enumerate(circuits, start=1) if c.get('description') == 'MISSING']
                
                logger.info(f"After AI enhancement: confidence={avg_confidence:.2f}, found={found_count}/{len(circuits)}")
        except Exception as e:
            logger.warning(f"AI fallback failed: {e}")
    
    return circuits, avg_confidence, missing_circuits
