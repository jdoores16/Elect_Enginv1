PANELBOARD OCR TEST FILES

Place your test files in this directory:

1. JPG/JPEG files - Photos of panelboard schedules
2. Excel files (.xlsx, .xlsm) - Existing panelboard schedules
3. PDF files - PDF documents containing panelboard schedules

The test script will process all files and generate Excel outputs in the 'out' directory.

Usage:
  python test_panelboard_ocr.py

Note: For PDF processing, you need to install pdf2image:
  pip install pdf2image
  (Also requires poppler-utils on your system)
