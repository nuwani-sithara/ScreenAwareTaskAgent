import cv2
import pytesseract

def extract_digits(crop):
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.threshold(gray, 0, 255,
                          cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    config = "--psm 6 -c tessedit_char_whitelist=0123456789"
    return pytesseract.image_to_string(gray, config=config).strip()
