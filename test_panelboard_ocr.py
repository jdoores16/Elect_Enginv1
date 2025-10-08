#!/usr/bin/env python3
"""
Test script for panelboard schedule OCR and Excel generation.
Tests processing from .jpg, .xlsx, and .pdf files.
"""

import sys
from pathlib import Path
from typing import List, Tuple
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import OCR and Excel utilities
from app.skills.ocr_panel import ocr_image_to_lines, parse_circuits_from_lines
from app.utils.excel_template import apply_template_to_data, find_template

# Constants
TEST_DIR = Path("test_panel_files")
OUTPUT_DIR = Path("out")
BUCKET_DIR = Path("bucket")


def test_jpg_ocr(jpg_path: Path, panel_name: str = "TEST_PANEL") -> Path:
    """
    Test OCR from JPG image file.
    
    Args:
        jpg_path: Path to JPG image of panelboard
        panel_name: Name for the panel
    
    Returns:
        Path to generated Excel file
    """
    logger.info(f"Testing JPG OCR: {jpg_path}")
    
    if not jpg_path.exists():
        raise FileNotFoundError(f"JPG file not found: {jpg_path}")
    
    # OCR the image
    lines = ocr_image_to_lines(jpg_path)
    logger.info(f"Extracted {len(lines)} lines from image")
    
    # Parse circuits
    circuits = parse_circuits_from_lines(lines)
    logger.info(f"Parsed {len(circuits)} circuits")
    
    # Generate Excel
    OUTPUT_DIR.mkdir(exist_ok=True)
    output_path = OUTPUT_DIR / f"{panel_name}_from_jpg.xlsx"
    
    # Look for template
    template = find_template(BUCKET_DIR, "")
    
    apply_template_to_data(circuits, panel_name, template, output_path)
    logger.info(f"✓ Generated Excel from JPG: {output_path}")
    
    return output_path


def test_excel_extraction(xlsx_path: Path, panel_name: str = "EXTRACTED_PANEL") -> Path:
    """
    Test extracting circuit data from existing Excel file.
    
    Args:
        xlsx_path: Path to existing Excel panelboard schedule
        panel_name: Name for the new panel
    
    Returns:
        Path to generated Excel file
    """
    logger.info(f"Testing Excel extraction: {xlsx_path}")
    
    if not xlsx_path.exists():
        raise FileNotFoundError(f"Excel file not found: {xlsx_path}")
    
    import openpyxl
    
    # Read existing Excel
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb.active
    
    circuits = []
    # Skip header row, start from row 2
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row and len(row) >= 2:
            # Try to extract circuit number and description
            circuit_num = str(row[0] if row[0] else row[1] if len(row) > 1 else "")
            description = str(row[1] if len(row) > 1 and row[1] else row[2] if len(row) > 2 and row[2] else "")
            
            if circuit_num and circuit_num.strip():
                circuits.append((circuit_num.strip(), description.strip()))
    
    logger.info(f"Extracted {len(circuits)} circuits from Excel")
    
    # Generate new Excel
    OUTPUT_DIR.mkdir(exist_ok=True)
    output_path = OUTPUT_DIR / f"{panel_name}_from_excel.xlsx"
    
    # Look for template
    template = find_template(BUCKET_DIR, "")
    
    apply_template_to_data(circuits, panel_name, template, output_path)
    logger.info(f"✓ Generated Excel from Excel: {output_path}")
    
    return output_path


def test_pdf_ocr(pdf_path: Path, panel_name: str = "PDF_PANEL") -> Path:
    """
    Test OCR from PDF file (converts PDF to images first).
    
    Args:
        pdf_path: Path to PDF containing panelboard schedule
        panel_name: Name for the panel
    
    Returns:
        Path to generated Excel file
    """
    logger.info(f"Testing PDF OCR: {pdf_path}")
    
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    try:
        from pdf2image import convert_from_path
    except ImportError:
        logger.error("pdf2image not installed. Install with: pip install pdf2image")
        logger.info("Skipping PDF test - install pdf2image and poppler to enable")
        raise
    
    # Convert PDF to images
    logger.info("Converting PDF to images...")
    images = convert_from_path(pdf_path, dpi=300)
    
    all_lines = []
    for i, img in enumerate(images):
        logger.info(f"Processing page {i+1}/{len(images)}")
        
        # Save temp image for OCR
        temp_img = OUTPUT_DIR / f"temp_page_{i}.jpg"
        img.save(temp_img, 'JPEG')
        
        # OCR the page
        lines = ocr_image_to_lines(temp_img)
        all_lines.extend(lines)
        
        # Clean up temp file
        temp_img.unlink()
    
    logger.info(f"Extracted {len(all_lines)} total lines from PDF")
    
    # Parse circuits
    circuits = parse_circuits_from_lines(all_lines)
    logger.info(f"Parsed {len(circuits)} circuits")
    
    # Generate Excel
    output_path = OUTPUT_DIR / f"{panel_name}_from_pdf.xlsx"
    
    # Look for template
    template = find_template(BUCKET_DIR, "")
    
    apply_template_to_data(circuits, panel_name, template, output_path)
    logger.info(f"✓ Generated Excel from PDF: {output_path}")
    
    return output_path


def run_all_tests():
    """Run all panelboard OCR tests."""
    logger.info("=" * 60)
    logger.info("PANELBOARD SCHEDULE OCR TEST SUITE")
    logger.info("=" * 60)
    
    # Create test directory if needed
    TEST_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    results = []
    
    # Test 1: JPG OCR
    logger.info("\n--- Test 1: JPG Image OCR ---")
    jpg_files = list(TEST_DIR.glob("*.jpg")) + list(TEST_DIR.glob("*.jpeg"))
    if jpg_files:
        for jpg in jpg_files:
            try:
                output = test_jpg_ocr(jpg, jpg.stem.upper())
                results.append(("JPG", jpg.name, "✓ PASS", str(output)))
            except Exception as e:
                results.append(("JPG", jpg.name, f"✗ FAIL: {e}", ""))
                logger.error(f"JPG test failed: {e}")
    else:
        logger.warning(f"No JPG files found in {TEST_DIR}. Place test images there.")
        results.append(("JPG", "N/A", "SKIP", "No test files"))
    
    # Test 2: Excel extraction
    logger.info("\n--- Test 2: Excel Extraction ---")
    xlsx_files = list(TEST_DIR.glob("*.xlsx")) + list(TEST_DIR.glob("*.xlsm"))
    if xlsx_files:
        for xlsx in xlsx_files:
            try:
                output = test_excel_extraction(xlsx, xlsx.stem.upper())
                results.append(("Excel", xlsx.name, "✓ PASS", str(output)))
            except Exception as e:
                results.append(("Excel", xlsx.name, f"✗ FAIL: {e}", ""))
                logger.error(f"Excel test failed: {e}")
    else:
        logger.warning(f"No Excel files found in {TEST_DIR}. Place test files there.")
        results.append(("Excel", "N/A", "SKIP", "No test files"))
    
    # Test 3: PDF OCR
    logger.info("\n--- Test 3: PDF OCR ---")
    pdf_files = list(TEST_DIR.glob("*.pdf"))
    if pdf_files:
        for pdf in pdf_files:
            try:
                output = test_pdf_ocr(pdf, pdf.stem.upper())
                results.append(("PDF", pdf.name, "✓ PASS", str(output)))
            except ImportError:
                results.append(("PDF", pdf.name, "SKIP", "pdf2image not installed"))
                logger.warning("PDF test skipped - install pdf2image")
                break
            except Exception as e:
                results.append(("PDF", pdf.name, f"✗ FAIL: {e}", ""))
                logger.error(f"PDF test failed: {e}")
    else:
        logger.warning(f"No PDF files found in {TEST_DIR}. Place test files there.")
        results.append(("PDF", "N/A", "SKIP", "No test files"))
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    
    for file_type, filename, status, output in results:
        logger.info(f"{file_type:8} | {filename:30} | {status:15} | {output}")
    
    logger.info("\n" + "=" * 60)
    logger.info(f"All outputs saved to: {OUTPUT_DIR.absolute()}")
    logger.info("=" * 60)


if __name__ == "__main__":
    try:
        run_all_tests()
    except KeyboardInterrupt:
        logger.info("\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Test suite failed: {e}", exc_info=True)
        sys.exit(1)
