"""
Generate Panel Schedule Variable List Excel file.

Creates a simple two-column spreadsheet listing all panel schedule
variables and their current values.
"""
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill

logger = logging.getLogger(__name__)


def generate_variable_list_excel(
    output_path: Path,
    panel_name: str,
    panel_specs: Dict[str, Any],
    circuits: Dict[str, Dict[str, Any]]
) -> Path:
    """
    Generate a variable list Excel file with all panel schedule parameters.
    
    Args:
        output_path: Path to save the Excel file
        panel_name: Panel identifier
        panel_specs: Dictionary of panel specifications (voltage, phase, etc.)
        circuits: Dictionary of circuit data keyed by circuit number
        
    Returns:
        Path to the generated Excel file
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Variable List"
    
    header_font = Font(bold=True, size=12)
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font_white = Font(bold=True, size=12, color="FFFFFF")
    border = Side(style='thin', color='000000')
    cell_border = Border(left=border, right=border, top=border, bottom=border)
    
    ws.column_dimensions['A'].width = 35
    ws.column_dimensions['B'].width = 40
    
    ws['A1'] = "Variable Name"
    ws['B1'] = "Value"
    ws['A1'].font = header_font_white
    ws['B1'].font = header_font_white
    ws['A1'].fill = header_fill
    ws['B1'].fill = header_fill
    ws['A1'].border = cell_border
    ws['B1'].border = cell_border
    ws['A1'].alignment = Alignment(horizontal='center')
    ws['B1'].alignment = Alignment(horizontal='center')
    
    row = 2
    
    section_font = Font(bold=True, size=11)
    section_fill = PatternFill(start_color="D9E2F3", end_color="D9E2F3", fill_type="solid")
    
    def add_section_header(title: str):
        nonlocal row
        ws.merge_cells(f'A{row}:B{row}')
        ws[f'A{row}'] = title
        ws[f'A{row}'].font = section_font
        ws[f'A{row}'].fill = section_fill
        ws[f'A{row}'].border = cell_border
        ws[f'B{row}'].border = cell_border
        row += 1
    
    def add_variable(name: str, value: Any):
        nonlocal row
        ws[f'A{row}'] = name
        ws[f'B{row}'] = str(value) if value is not None else ""
        ws[f'A{row}'].border = cell_border
        ws[f'B{row}'].border = cell_border
        ws[f'A{row}'].alignment = Alignment(horizontal='left')
        ws[f'B{row}'].alignment = Alignment(horizontal='left')
        row += 1
    
    add_section_header("PANEL IDENTIFICATION")
    add_variable("Panel Name", panel_name)
    
    add_section_header("PANEL SPECIFICATIONS")
    add_variable("Voltage", panel_specs.get("voltage", ""))
    add_variable("Phase", panel_specs.get("phase", ""))
    add_variable("Wire", panel_specs.get("wire", ""))
    add_variable("Main Bus Amps", panel_specs.get("main_bus_amps", ""))
    add_variable("Main Circuit Breaker", panel_specs.get("main_breaker", ""))
    add_variable("Mounting", panel_specs.get("mounting", ""))
    add_variable("Feed", panel_specs.get("feed", ""))
    add_variable("Location", panel_specs.get("location", ""))
    add_variable("Fed From", panel_specs.get("fed_from", ""))
    add_variable("Number of Circuits", panel_specs.get("number_of_ckts", len(circuits)))
    
    if circuits:
        add_section_header("CIRCUIT DATA")
        
        sorted_circuits = sorted(circuits.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999)
        
        for circuit_num, circuit_data in sorted_circuits:
            if circuit_data.get('is_continuation'):
                continue
                
            desc = circuit_data.get('description', '')
            breaker_amps = circuit_data.get('breaker_amps', 0)
            poles = circuit_data.get('poles', 1)
            load_amps = circuit_data.get('load_amps', 0)
            
            add_variable(f"Pole Space {circuit_num} Description", desc)
            add_variable(f"Pole Space {circuit_num} Breaker Amps", f"{breaker_amps}A" if breaker_amps else "")
            add_variable(f"Pole Space {circuit_num} Poles", f"{poles}P" if poles else "")
            if load_amps:
                add_variable(f"Pole Space {circuit_num} Load Amps", f"{load_amps}A")
    
    ws.freeze_panes = 'A2'
    
    wb.save(output_path)
    logger.info(f"Generated variable list Excel: {output_path}")
    
    return output_path
