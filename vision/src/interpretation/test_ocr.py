import cv2
import pytesseract
import numpy as np

# Uncomment if needed
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

img = cv2.imread("data/detected_images/frame_1765771009.jpg")

crop = img[150:190, 210:260]
cv2.imshow("original", crop)

gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
cv2.imshow("gray", gray)

# Resize aggressively
gray = cv2.resize(gray, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
cv2.imshow("resized", gray)

# Increase contrast instead of threshold
alpha = 2.5   # contrast
beta = -200   # brightness
enhanced = cv2.convertScaleAbs(gray, alpha=alpha, beta=beta)
cv2.imshow("enhanced", enhanced)

cv2.imwrite("debug_ocr_input.png", enhanced)

# OCR CONFIG FOR 2048 TILES
config = "--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789"

text = pytesseract.image_to_string(enhanced, config=config)

print("RAW OCR repr:", repr(text))
digits = "".join(c for c in text if c.isdigit())
print("EXTRACTED:", repr(digits))

if digits:
    print("OCR SUCCESS:", digits)
else:
    print("OCR FAILED")

cv2.waitKey(0)
cv2.destroyAllWindows()
