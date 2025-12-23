import cv2
import pytesseract
import logging

# If Windows, set the Tesseract executable path (only needed if not in PATH)
pytesseract.pytesseract.tesseract_cmd = r"C:\Users\PM_User\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"

def perceive():
    print("👁️ Perceiving screen (OCR)...")
    logging.info("👁️ Perceiving screen with OCR...")

    # STEP 1: Load an image (temporary mock for screenshot/camera)
    screenshot = cv2.imread("backend/core/sample_screen.png")  # <-- use any .png/.jpg for testing

    if screenshot is None:
        logging.error("❌ Screenshot not found!")
        return {"screen_text": ""}

    # STEP 2: Convert to grayscale (improves OCR accuracy)
    gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)

    # STEP 3: Apply OCR
    extracted_text = pytesseract.image_to_string(gray)

    # STEP 4: Log and return OCR result
    logging.info(f"📄 OCR Extracted Text: {extracted_text.strip()}")
    return {"screen_text": extracted_text.strip()}
