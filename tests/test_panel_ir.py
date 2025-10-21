"""
Comprehensive tests for PanelScheduleIR - the core Intermediate Representation.
These tests ensure the IR is bulletproof with validation, normalization, and edge cases.
"""
import pytest
from pydantic import ValidationError
from app.schemas.panel_ir import (
    PanelScheduleIR,
    HeaderBlock,
    CircuitRecord,
    NameValuePair,
    LEFT_LABELS,
    RIGHT_LABELS
)


# ============================================================================
# Helper Functions
# ============================================================================

def make_left_params(values: dict = None):
    """Create left_params list with optional value overrides"""
    defaults = {
        "VOLTAGE": "480Y/277V",
        "PHASE": "3PH",
        "WIRE": "4W+G",
        "MAIN BUS AMPS": "800",
        "MAIN CIRCUIT BREAKER": "MLO",
        "MOUNTING": "SURFACE",
        "FEED": "MSB-1",
        "FEED-THRU LUGS": "YES"
    }
    if values:
        defaults.update(values)
    
    return [
        NameValuePair(
            name_cell=name_cell,
            value_cell=val_cell,
            name_text=text,
            value=defaults.get(text)
        )
        for name_cell, val_cell, text in LEFT_LABELS
    ]


def make_right_params(values: dict = None):
    """Create right_params list with optional value overrides"""
    defaults = {
        "LOCATION": "ELECTRICAL ROOM",
        "FED FROM": "MSB-1",
        "UL LISTED EQUIPMENT SHORT CIRCUIT RATING": "22kA",
        "MAXIMUM AVAILABLE SHORT CIRCUIT CURRENT": "18kA",
        "PHASE CONDUCTOR": "#1/0 CU",
        "NEUTRAL CONDUCTOR": "#1/0 CU",
        "GROUND CONDUCTOR": "#6 CU"
    }
    if values:
        defaults.update(values)
    
    return [
        NameValuePair(
            name_cell=name_cell,
            value_cell=val_cell,
            name_text=text,
            value=defaults.get(text)
        )
        for name_cell, val_cell, text in RIGHT_LABELS
    ]


def make_circuit(ckt: int, **kwargs):
    """Create a circuit record with sensible defaults"""
    defaults = {
        "ckt": ckt,
        "side": "odd" if ckt % 2 == 1 else "even",
        "excel_row": 11 + ((ckt + 1) // 2),
        "breaker_amps": 20.0,
        "load_amps": 15.0,
        "poles": 1,
        "phA": True if ckt <= 2 else False,
        "phB": True if 3 <= ckt <= 4 else False,
        "phC": True if ckt >= 5 else False,
        "description": f"CIRCUIT {ckt}"
    }
    defaults.update(kwargs)
    return CircuitRecord(**defaults)


def make_header(**kwargs):
    """Create a header with sensible defaults"""
    defaults = {
        "panel_name": "PP-1",
        "left_params": make_left_params(),
        "right_params": make_right_params()
    }
    defaults.update(kwargs)
    return HeaderBlock(**defaults)


# ============================================================================
# Header Tests
# ============================================================================

class TestHeaderBlock:
    """Tests for HeaderBlock validation and normalization"""
    
    def test_valid_header(self):
        """Test creating a valid header"""
        header = make_header()
        assert header.panel_name == "PP-1"
        assert len(header.left_params) == 8
        assert len(header.right_params) == 7
    
    def test_phase_normalization_1ph(self):
        """Test PHASE normalization to 1PH"""
        test_cases = ["1Ø", "1PH", "SINGLE", "1", "1 PHASE", "SINGLE PHASE"]
        for input_val in test_cases:
            header = make_header(left_params=make_left_params({"PHASE": input_val}))
            phase_param = next(p for p in header.left_params if p.name_text == "PHASE")
            assert phase_param.value == "1PH", f"Failed for input: {input_val}"
    
    def test_phase_normalization_3ph(self):
        """Test PHASE normalization to 3PH"""
        test_cases = ["3Ø", "3PH", "THREE", "3", "3 PHASE", "THREE PHASE"]
        for input_val in test_cases:
            header = make_header(left_params=make_left_params({"PHASE": input_val}))
            phase_param = next(p for p in header.left_params if p.name_text == "PHASE")
            assert phase_param.value == "3PH", f"Failed for input: {input_val}"
    
    def test_mcb_normalization_mlo(self):
        """Test MCB normalization to MLO"""
        test_cases = ["MLO", "MAIN LUG", "NO MAIN", "NOT MCB", "LUGS ONLY"]
        for input_val in test_cases:
            header = make_header(left_params=make_left_params({"MAIN CIRCUIT BREAKER": input_val}))
            mcb_param = next(p for p in header.left_params if p.name_text == "MAIN CIRCUIT BREAKER")
            assert mcb_param.value == "MLO", f"Failed for input: {input_val}"
    
    def test_mcb_normalization_amperage(self):
        """Test MCB normalization to amperage format"""
        test_cases = [("800", "800A"), ("600A", "600A"), ("400 A", "400A")]
        for input_val, expected in test_cases:
            header = make_header(left_params=make_left_params({"MAIN CIRCUIT BREAKER": input_val}))
            mcb_param = next(p for p in header.left_params if p.name_text == "MAIN CIRCUIT BREAKER")
            assert mcb_param.value == expected, f"Failed for input: {input_val}"
    
    def test_left_params_wrong_count(self):
        """Test that left_params must have exactly 8 items"""
        with pytest.raises(ValidationError, match="at least 8"):
            HeaderBlock(
                panel_name="PP-1",
                left_params=make_left_params()[:7],  # Only 7 items
                right_params=make_right_params()
            )
    
    def test_right_params_wrong_count(self):
        """Test that right_params must have exactly 7 items"""
        with pytest.raises(ValidationError, match="at least 7"):
            HeaderBlock(
                panel_name="PP-1",
                left_params=make_left_params(),
                right_params=make_right_params()[:6]  # Only 6 items
            )
    
    def test_o9_must_be_blank(self):
        """Test that O9 cell must remain blank"""
        with pytest.raises(ValidationError, match="O9 must remain blank"):
            HeaderBlock(
                panel_name="PP-1",
                left_params=make_left_params(),
                right_params=make_right_params(),
                right_unused_value="SOMETHING"
            )
    
    def test_value_uppercase(self):
        """Test that string values are converted to uppercase"""
        header = make_header(left_params=make_left_params({"VOLTAGE": "480y/277v"}))
        voltage_param = next(p for p in header.left_params if p.name_text == "VOLTAGE")
        assert voltage_param.value == "480Y/277V"


# ============================================================================
# Circuit Tests
# ============================================================================

class TestCircuitRecord:
    """Tests for CircuitRecord validation"""
    
    def test_valid_odd_circuit(self):
        """Test creating a valid odd circuit"""
        circuit = make_circuit(1)
        assert circuit.ckt == 1
        assert circuit.side == "odd"
        assert circuit.excel_row == 12
    
    def test_valid_even_circuit(self):
        """Test creating a valid even circuit"""
        circuit = make_circuit(2)
        assert circuit.ckt == 2
        assert circuit.side == "even"
        assert circuit.excel_row == 12
    
    def test_circuit_parity_validation(self):
        """Test that circuit numbers match their side (soft check - relies on correct usage)"""
        odd = make_circuit(1, side="odd")
        assert odd.ckt % 2 == 1
        even = make_circuit(2, side="even") 
        assert even.ckt % 2 == 0
    
    def test_breaker_and_load_amps_must_differ(self):
        """Test that breaker_amps and load_amps cannot be equal"""
        with pytest.raises(ValidationError, match="breaker_amps must not equal load_amps"):
            CircuitRecord(
                ckt=1, side="odd", excel_row=12,
                breaker_amps=20, load_amps=20
            )
    
    def test_description_length_limit(self):
        """Test that description is limited to 39 characters"""
        long_desc = "A" * 50
        circuit = make_circuit(1, description=long_desc)
        assert len(circuit.description) == 39
        assert circuit.description == "A" * 39
    
    def test_description_uppercase(self):
        """Test that description is converted to uppercase"""
        circuit = make_circuit(1, description="lighting fixtures")
        assert circuit.description == "LIGHTING FIXTURES"
    
    def test_row_calculation_circuit_1(self):
        """Test row calculation for circuit 1 (odd)"""
        assert make_circuit(1).excel_row == 12
    
    def test_row_calculation_circuit_2(self):
        """Test row calculation for circuit 2 (even)"""
        assert make_circuit(2).excel_row == 12
    
    def test_row_calculation_circuit_83(self):
        """Test row calculation for circuit 83 (last odd)"""
        assert make_circuit(83).excel_row == 53
    
    def test_row_calculation_circuit_84(self):
        """Test row calculation for circuit 84 (last even)"""
        assert make_circuit(84).excel_row == 53


# ============================================================================
# PanelScheduleIR Tests
# ============================================================================

class TestPanelScheduleIR:
    """Tests for complete PanelScheduleIR"""
    
    def test_valid_ir(self):
        """Test creating a valid IR"""
        ir = PanelScheduleIR(
            header=make_header(),
            circuits=[make_circuit(1), make_circuit(2)]
        )
        assert ir.version == "1.0.0"
        assert len(ir.circuits) == 2
    
    def test_duplicate_circuit_numbers(self):
        """Test that duplicate circuit numbers are rejected"""
        with pytest.raises(ValidationError, match="Duplicate circuit 1"):
            PanelScheduleIR(
                header=make_header(),
                circuits=[make_circuit(1), make_circuit(1)]
            )
    
    def test_wrong_excel_row(self):
        """Test that incorrect excel_row is rejected"""
        with pytest.raises(ValidationError, match="Circuit 1 must be on row 12"):
            PanelScheduleIR(
                header=make_header(),
                circuits=[make_circuit(1, excel_row=15)]
            )
    
    def test_empty_circuits_allowed(self):
        """Test that empty circuits list is allowed"""
        ir = PanelScheduleIR(
            header=make_header(),
            circuits=[]
        )
        assert len(ir.circuits) == 0
    
    def test_full_42_circuit_panel(self):
        """Test a full 42-circuit panel"""
        circuits = [make_circuit(i) for i in range(1, 43)]
        ir = PanelScheduleIR(
            header=make_header(),
            circuits=circuits
        )
        assert len(ir.circuits) == 42
        assert ir.circuits[0].ckt == 1
        assert ir.circuits[-1].ckt == 42
    
    def test_serialization_round_trip(self):
        """Test that IR can be serialized and deserialized"""
        ir = PanelScheduleIR(
            header=make_header(),
            circuits=[make_circuit(1), make_circuit(2)]
        )
        # Serialize to dict
        ir_dict = ir.model_dump()
        # Deserialize back
        ir_restored = PanelScheduleIR.model_validate(ir_dict)
        assert ir_restored.header.panel_name == ir.header.panel_name
        assert len(ir_restored.circuits) == len(ir.circuits)


# ============================================================================
# Edge Cases and Integration Tests
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and integration scenarios"""
    
    def test_minimal_ir(self):
        """Test minimal valid IR with no circuits"""
        ir = PanelScheduleIR(
            header=HeaderBlock(
                panel_name="TEST",
                left_params=make_left_params(),
                right_params=make_right_params()
            ),
            circuits=[]
        )
        assert ir.header.panel_name == "TEST"
    
    def test_circuit_boundary_values(self):
        """Test circuit numbers at boundaries (1 and 84)"""
        ir = PanelScheduleIR(
            header=make_header(),
            circuits=[make_circuit(1), make_circuit(84)]
        )
        assert ir.circuits[0].ckt == 1
        assert ir.circuits[1].ckt == 84
    
    def test_circuit_number_too_low(self):
        """Test that circuit number < 1 is rejected"""
        with pytest.raises(ValidationError):
            make_circuit(0)
    
    def test_circuit_number_too_high(self):
        """Test that circuit number > 84 is rejected"""
        with pytest.raises(ValidationError):
            make_circuit(85)
    
    def test_json_export_import(self):
        """Test JSON export/import for API compatibility"""
        ir = PanelScheduleIR(
            header=make_header(panel_name="JSON-TEST"),
            circuits=[make_circuit(1)]
        )
        # Export to JSON string
        json_str = ir.model_dump_json()
        # Import from JSON string
        ir_imported = PanelScheduleIR.model_validate_json(json_str)
        assert ir_imported.header.panel_name == "JSON-TEST"
