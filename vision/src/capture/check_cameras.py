import cv2

def check_cameras(max_tested=5):
    print("Scanning for available cameras...")
    for i in range(max_tested):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            print(f"Camera index {i} is working")
            ret, frame = cap.read()
            if ret:
                cv2.imshow(f"Camera {i}", frame)
                cv2.waitKey(1000)  # show frame for 1 second
                cv2.destroyWindow(f"Camera {i}")
            cap.release()
        else:
            print(f"Camera index {i} not available")

if __name__ == "__main__":
    check_cameras()
