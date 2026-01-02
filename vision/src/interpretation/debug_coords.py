import cv2

def mouse_callback(event, x, y, flags, param):
    if event == cv2.EVENT_MOUSEMOVE:
        print(f"x={x}, y={y}")

img = cv2.imread("data/detected_images/frame_1765771009.jpg")

cv2.imshow("image", img)
cv2.setMouseCallback("image", mouse_callback)
cv2.waitKey(0)
cv2.destroyAllWindows()
