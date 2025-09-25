import pytesseract
from PIL import Image
import sys

def main():
    if len(sys.argv) < 2:
        print("Usage: python ocr_quicktest.py <image_file>")
        sys.exit(1)

    img_path = sys.argv[1]
    print(f"[INFO] Running OCR on {img_path} ...")

    # Open and run OCR
    img = Image.open(img_path)
    text = pytesseract.image_to_string(img)

    print("\n--- OCR OUTPUT ---")
    print(text)

if __name__ == "__main__":
    main()