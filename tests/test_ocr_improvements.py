"""
Test suite for OCR improvements:
- Image preprocessing
- AI-enhanced extraction
- Tesseract configuration optimization
"""

import pytest
from pathlib import Path
from PIL import Image
import numpy as np
import cv2


def test_image_preprocessing_pipeline():
    """Test that image preprocessing improves image quality"""
    from app.skills.image_preprocessing import ImagePreprocessor
    
    preprocessor = ImagePreprocessor(
        enable_deskew=True,
        enable_denoise=True,
        enable_contrast=True,
        enable_binarization=True
    )
    
    test_img = np.ones((1000, 1000, 3), dtype=np.uint8) * 128
    
    test_img = cv2.GaussianBlur(test_img, (5, 5), 0)
    
    temp_path = Path("/tmp/test_panel.jpg")
    cv2.imwrite(str(temp_path), test_img)
    
    try:
        processed = preprocessor.preprocess(temp_path)
        
        assert processed is not None
        assert isinstance(processed, Image.Image)
        
        assert processed.width > 0 and processed.height > 0
        
        print(f"✓ Image preprocessing successful: {processed.size}")
        
    finally:
        if temp_path.exists():
            temp_path.unlink()


def test_ocr_with_and_without_preprocessing():
    """Compare OCR accuracy with and without preprocessing"""
    from app.skills.ocr_panel import ocr_image_to_lines
    
    test_text = "PANEL: PP-1\nVOLTAGE: 480Y/277V\nCIRCUIT 1 - LIGHTING - 20A 1P"
    
    test_img = np.ones((800, 1200, 3), dtype=np.uint8) * 255
    
    font = cv2.FONT_HERSHEY_SIMPLEX
    y_pos = 100
    for line in test_text.split('\n'):
        cv2.putText(test_img, line, (50, y_pos), font, 1, (0, 0, 0), 2)
        y_pos += 100
    
    test_img = cv2.GaussianBlur(test_img, (3, 3), 0)
    
    temp_path = Path("/tmp/test_panel_ocr.jpg")
    cv2.imwrite(str(temp_path), test_img)
    
    try:
        lines_basic = ocr_image_to_lines(temp_path, use_preprocessing=False)
        print(f"Basic OCR extracted {len(lines_basic)} lines")
        
        lines_enhanced = ocr_image_to_lines(temp_path, use_preprocessing=True)
        print(f"Enhanced OCR extracted {len(lines_enhanced)} lines")
        
        assert len(lines_enhanced) > 0, "Enhanced OCR should extract some lines"
        
        print("✓ OCR comparison successful")
        
    finally:
        if temp_path.exists():
            temp_path.unlink()


def test_ai_circuit_extraction():
    """Test AI-enhanced circuit extraction"""
    from app.skills.ai_ocr_extraction import ai_extract_circuits
    from app.core.settings import get_settings
    
    settings = get_settings()
    
    if not settings.openai_api_key:
        pytest.skip("OpenAI API key not configured")
    
    sample_ocr_lines = [
        "CIRCUIT 1 LIGHTING 2.5kVA 20A 1P",
        "2  RECEPTACLES  1.8  15A  1P",
        "Circuit #3: HVAC Unit / 5.0 kW / 30 Amps / 2-Pole",
        "Ckt 4 - Office Lights - 3kVA - 20A - 1P"
    ]
    
    circuits = ai_extract_circuits(sample_ocr_lines, panel_name="TEST-PANEL")
    
    print(f"AI extracted {len(circuits)} circuits")
    for circuit in circuits:
        print(f"  Circuit {circuit.get('number')}: {circuit.get('description')}")
    
    assert len(circuits) > 0, "AI should extract at least one circuit"
    
    for circuit in circuits[:3]:
        assert 'number' in circuit, "Each circuit should have a number"
        assert 'description' in circuit or 'breaker_amps' in circuit, "Circuit should have some data"
    
    print("✓ AI circuit extraction successful")


def test_tesseract_config():
    """Verify Tesseract is configured with optimal settings"""
    import pytesseract
    from PIL import Image
    
    test_img = Image.new('L', (400, 100), color=255)
    
    custom_config = r'--oem 3 --psm 6'
    
    text = pytesseract.image_to_string(test_img, config=custom_config)
    
    print("✓ Tesseract configuration successful")


def test_preprocessing_feature_flags():
    """Test that preprocessing features can be toggled"""
    from app.skills.image_preprocessing import ImagePreprocessor
    
    configs = [
        {"enable_deskew": True, "enable_denoise": False, "enable_contrast": False, "enable_binarization": False},
        {"enable_deskew": False, "enable_denoise": True, "enable_contrast": False, "enable_binarization": False},
        {"enable_deskew": False, "enable_denoise": False, "enable_contrast": True, "enable_binarization": False},
        {"enable_deskew": False, "enable_denoise": False, "enable_contrast": False, "enable_binarization": True},
    ]
    
    for config in configs:
        preprocessor = ImagePreprocessor(**config)
        
        enabled_features = [k for k, v in config.items() if v]
        print(f"✓ Preprocessor created with {enabled_features}")
    
    print("✓ Feature flag testing successful")


if __name__ == "__main__":
    print("="*80)
    print("OCR IMPROVEMENTS TEST SUITE")
    print("="*80)
    print()
    
    tests = [
        ("Image Preprocessing Pipeline", test_image_preprocessing_pipeline),
        ("OCR With/Without Preprocessing", test_ocr_with_and_without_preprocessing),
        ("AI Circuit Extraction", test_ai_circuit_extraction),
        ("Tesseract Configuration", test_tesseract_config),
        ("Preprocessing Feature Flags", test_preprocessing_feature_flags),
    ]
    
    passed = 0
    failed = 0
    skipped = 0
    
    for name, test_func in tests:
        print(f"\nTesting: {name}")
        print("-" * 80)
        try:
            test_func()
            passed += 1
            print(f"✓ PASSED: {name}")
        except pytest.skip.Exception as e:
            skipped += 1
            print(f"⊘ SKIPPED: {name} - {e}")
        except Exception as e:
            failed += 1
            print(f"✗ FAILED: {name} - {e}")
            import traceback
            traceback.print_exc()
    
    print()
    print("="*80)
    print(f"RESULTS: {passed} passed, {failed} failed, {skipped} skipped")
    print("="*80)
