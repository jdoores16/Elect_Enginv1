# app/ai/checklist.py
from __future__ import annotations
from typing import List, Dict, Any
from app.schemas.panel_ir import PanelScheduleIR, NameValuePair

def _get_left(ir: PanelScheduleIR, label: str) -> str:
    for p in ir.header.left_params:
        if p.name_text.strip().upper() == label.upper():
            return "" if p.value is None else str(p.value)
    return ""

def _get_right(ir: PanelScheduleIR, label: str) -> str:
    for p in ir.header.right_params:
        if p.name_text.strip().upper() == label.upper():
            return "" if p.value is None else str(p.value)
    return ""

def build_checklist(ir: PanelScheduleIR) -> List[str]:
    """
    Technical electrical engineering checks - NO formatting/aesthetics.
    Focus on electrical system design, safety, code compliance, and engineering validity.
    """
    voltage = _get_left(ir, "VOLTAGE")
    phase   = _get_left(ir, "PHASE")
    wire    = _get_left(ir, "WIRE")
    main_bus = _get_left(ir, "MAIN BUS AMPS")
    mcb      = _get_left(ir, "MAIN CIRCUIT BREAKER")
    
    location = _get_right(ir, "LOCATION")
    fed_from = _get_right(ir, "FED FROM")
    phase_conductor = _get_right(ir, "PHASE CONDUCTOR")
    neutral_conductor = _get_right(ir, "NEUTRAL CONDUCTOR")
    ground_conductor = _get_right(ir, "GROUND CONDUCTOR")
    
    checks = [
        # System Type Analysis
        f"Based on VOLTAGE '{voltage}', determine if this is a DELTA or WYE system. Verify voltage notation is correct for system type.",
        
        # Grounding & Neutral Analysis
        f"Analyze if system is grounded or ungrounded based on WIRE '{wire}' and VOLTAGE '{voltage}'.",
        f"Verify if neutral conductor is required for this system type. Check if NEUTRAL CONDUCTOR '{neutral_conductor}' is appropriate.",
        
        # Phase & Wire Configuration
        f"For PHASE '{phase}' and WIRE '{wire}', verify wire configuration matches phase requirements (e.g., 3PH needs 3W or 4W).",
        
        # Conductor Sizing
        f"Validate PHASE CONDUCTOR '{phase_conductor}' sizing is adequate for MAIN BUS AMPS '{main_bus}'.",
        f"Validate NEUTRAL CONDUCTOR '{neutral_conductor}' sizing meets NEC requirements for this load.",
        f"Validate GROUND CONDUCTOR '{ground_conductor}' sizing meets NEC Article 250 requirements.",
        
        # Main Circuit Breaker vs Bus Analysis
        f"Verify MAIN CIRCUIT BREAKER '{mcb}' relationship to MAIN BUS AMPS '{main_bus}'. Check for oversizing or undersizing.",
        
        # Phase Balance Analysis
        "Calculate total phase loads for Phase A, Phase B, and Phase C. Verify phase balance is within acceptable limits (±20%).",
        
        # Amperage & KVA Conversion
        f"Calculate total KVA based on voltage '{voltage}', phase '{phase}', and total amperage. Verify conversion is correct.",
        
        # Individual Phase Amp Validation
        f"For each phase (A, B, C), verify total connected load does not exceed MAIN BUS AMPS '{main_bus}'.",
        
        # Circuit Breaker Coordination
        "Verify all branch circuit breakers are properly sized for their connected loads (NEC 210.20).",
        
        # Panel Usage & Location Insights
        f"Based on LOCATION '{location}' and circuit descriptions, analyze appropriate panel usage and environmental considerations.",
        
        # Material & Construction
        f"Based on panel application, location '{location}', and loading, recommend appropriate enclosure type (NEMA rating).",
        
        # Upstream Coordination
        f"Analyze if FED FROM '{fed_from}' provides adequate source capacity for this panel's total load.",
    ]
    
    return checks

def summarize_for_gpt(ir: PanelScheduleIR) -> str:
    """
    Comprehensive electrical engineering data dump for technical review.
    Include all electrical parameters needed for analysis.
    """
    def fmt_pair(p: NameValuePair) -> str:
        return f"- {p.name_text}: {p.value if p.value is not None else 'NOT SPECIFIED'}"

    left = "\n".join(fmt_pair(p) for p in ir.header.left_params)
    right = "\n".join(fmt_pair(p) for p in ir.header.right_params)

    lines = [
        f"# PANEL SCHEDULE: {ir.header.panel_name}",
        "",
        "## ELECTRICAL SYSTEM PARAMETERS:",
        left,
        "",
        "## INSTALLATION & PROTECTION:",
        right,
        "",
        "## CIRCUIT LOADING ANALYSIS:",
    ]
    
    # Calculate phase totals for analysis
    phase_a_total = sum(c.load_amps for c in ir.circuits if c.phA and c.load_amps)
    phase_b_total = sum(c.load_amps for c in ir.circuits if c.phB and c.load_amps)
    phase_c_total = sum(c.load_amps for c in ir.circuits if c.phC and c.load_amps)
    
    lines.append(f"Phase A Total Load: {phase_a_total:.1f}A")
    lines.append(f"Phase B Total Load: {phase_b_total:.1f}A")
    lines.append(f"Phase C Total Load: {phase_c_total:.1f}A")
    lines.append("")
    
    # Show all circuits for complete analysis
    lines.append(f"## ALL CIRCUITS ({len(ir.circuits)} total):")
    for rec in sorted(ir.circuits, key=lambda x: x.ckt):
        phases = []
        if rec.phA: phases.append('A')
        if rec.phB: phases.append('B')
        if rec.phC: phases.append('C')
        phase_str = ','.join(phases) if phases else 'NONE'
        
        lines.append(
            f"CKT {rec.ckt:>2}: {rec.description or 'NO DESCRIPTION':<40} | "
            f"Breaker: {rec.breaker_amps}A | Load: {rec.load_amps}A | "
            f"Poles: {rec.poles or '?'} | Phase(s): {phase_str}"
        )
    
    return "\n".join(lines)
