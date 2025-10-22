"""
ipcam_capture.py
Capture frames from mobile IP camera (using IP Webcam app) and save images.
"""

import cv2
import os
import time

def start_ipcam_capture(ip_address, save_dir="data/raw_frames", interval=2):
    os.makedirs(save_dir, exist_ok=True)
    url = f"http://{ip_address}:8080/video"

    cap = cv2.VideoCapture(url)
    if not cap.isOpened():
        print("❌ Unable to open video stream. Check IP or connection.")
        return

    print("✅ Connected to camera. Press 's' to save manually, 'a' for auto-save, 'q' to quit.")
    auto_save = False
    last_saved = 0
    saved_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            print("⚠️ Frame not received. Retrying...")
            time.sleep(0.5)
            continue

        cv2.imshow("IP Camera Feed", frame)
        key = cv2.waitKey(1) & 0xFF

        if key == ord('s'):
            filename = os.path.join(save_dir, f"frame_{int(time.time())}.jpg")
            cv2.imwrite(filename, frame)
            saved_count += 1
            print(f"💾 Saved: {filename}")

        if key == ord('a'):
            auto_save = not auto_save
            print("Auto-save:", auto_save)

        if auto_save and time.time() - last_saved > interval:
            filename = os.path.join(save_dir, f"frame_{int(time.time())}.jpg")
            cv2.imwrite(filename, frame)
            saved_count += 1
            last_saved = time.time()
            print(f"💾 Auto-saved: {filename}")

        if key == ord('q'):
            break

    print(f"✅ Done. Total saved images: {saved_count}")
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    ip = input("Enter your phone IP (e.g., 192.168.1.5): ")
    start_ipcam_capture(ip)
