"""
Test the technical electrical engineering review (not formatting review).
Verifies that OpenAI receives proper technical checklist and data.
"""

import pytest
from app.ai.checklist import build_checklist, summarize_for_gpt, _get_left, _get_right


def test_checklist_content_is_technical():
    """Verify checklist contains electrical engineering terms"""
    from tests.test_panel_ir import make_simple_ir
    
    ir = make_simple_ir(voltage="480Y/277V", phase="3PH", wire="4W+G", main_bus="800", mcb="400A")
    checklist = build_checklist(ir)
    
    # Should contain electrical engineering checks
    checklist_text = " ".join(checklist).upper()
    
    assert "DELTA" in checklist_text or "WYE" in checklist_text, "Should analyze DELTA vs WYE"
    assert "GROUNDED" in checklist_text or "UNGROUNDED" in checklist_text, "Should check grounding"
    assert "NEUTRAL" in checklist_text, "Should verify neutral requirements"
    assert "PHASE" in checklist_text, "Should check phase configuration"
    assert "CONDUCTOR" in checklist_text, "Should validate conductor sizing"
    assert "KVA" in checklist_text, "Should verify KVA calculation"
    assert "BALANCE" in checklist_text, "Should check phase balance"
    assert "NEC" in checklist_text, "Should reference NEC code"
    
    print("\n✓ Checklist includes technical electrical terms")


def test_checklist_avoids_formatting():
    """Verify checklist does NOT check formatting/aesthetics"""
    from tests.test_panel_ir import make_simple_ir
    
    ir = make_simple_ir()
    checklist = build_checklist(ir)
    checklist_text = " ".join(checklist).upper()
    
    # Should NOT contain formatting checks
    assert "FONT" not in checklist_text, "Should NOT check fonts"
    assert "COLOR" not in checklist_text, "Should NOT check colors"
    assert "AESTHETIC" not in checklist_text, "Should NOT check aesthetics"
    
    print("\n✓ Checklist avoids formatting/aesthetic checks")


def test_summary_calculates_phase_totals():
    """Verify summary includes phase load calculations"""
    from tests.test_panel_ir import make_simple_ir
    
    ir = make_simple_ir()
    summary = summarize_for_gpt(ir)
    
    # Should include phase totals
    assert "Phase A Total Load:" in summary
    assert "Phase B Total Load:" in summary
    assert "Phase C Total Load:" in summary
    assert "ALL CIRCUITS" in summary
    
    print("\n✓ Summary includes phase load calculations")


def test_checklist_references_actual_values():
    """Verify checklist uses actual panel values for analysis"""
    from tests.test_panel_ir import make_simple_ir
    
    ir = make_simple_ir(voltage="208/120V", phase="1PH", wire="3W+G", main_bus="225", mcb="200A")
    checklist = build_checklist(ir)
    checklist_text = " ".join(checklist)
    
    # Should reference actual values from the panel
    assert "208/120V" in checklist_text, "Should reference actual voltage"
    assert "225" in checklist_text, "Should reference actual main bus amps"
    assert "200A" in checklist_text or "MLO" in checklist_text, "Should reference actual MCB"
    
    print("\n✓ Checklist uses actual panel parameter values")


def test_helper_functions():
    """Test helper functions work correctly"""
    from tests.test_panel_ir import make_simple_ir
    
    ir = make_simple_ir(voltage="480Y/277V")
    
    voltage = _get_left(ir, "VOLTAGE")
    assert voltage == "480Y/277V"
    
    location = _get_right(ir, "LOCATION") 
    # Should return empty string if not found, or actual value if present
    assert isinstance(location, str)
    
    print("\n✓ Helper functions extract parameters correctly")


def test_checklist_has_minimum_required_items():
    """Verify checklist has sufficient technical review items"""
    from tests.test_panel_ir import make_simple_ir
    
    ir = make_simple_ir()
    checklist = build_checklist(ir)
    
    # Should have at least 10 technical checks
    assert len(checklist) >= 10, f"Expected at least 10 technical checks, got {len(checklist)}"
    
    # Each item should be a meaningful string
    for item in checklist:
        assert len(item) > 20, "Each checklist item should be descriptive"
    
    print(f"\n✓ Checklist has {len(checklist)} technical review items")
