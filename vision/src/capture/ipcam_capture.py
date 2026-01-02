import cv2
import os
import time

def start_capture(ip_address, save_dir="data/raw_frames", mode="auto", interval=1):
    os.makedirs(save_dir, exist_ok=True)
    url = f"http://{ip_address}:8080/video"
    cap = cv2.VideoCapture(url)

    if not cap.isOpened():
        print("Unable to connect to camera. Check IP.")
        return

    print(f"Connected to {ip_address}")
    print(f"Mode: {mode.upper()} | Interval: {interval}s")
    print("Press 'q' to stop capturing.\n")

    last_saved = 0
    count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Frame not received. Retrying...")
            time.sleep(0.5)
            continue

        # Display live feed
        cv2.imshow("Visual Perception Capture", frame)

        # --- Continuous Mode ---
        if mode == "auto":
            current_time = time.time()
            if current_time - last_saved >= interval:
                filename = os.path.join(save_dir, f"frame_{int(current_time)}.jpg")
                cv2.imwrite(filename, frame)
                last_saved = current_time
                count += 1
                print(f"Auto-saved: {filename}")

        # --- Selective Mode (press 's' to capture important frames) ---
        elif mode == "selective":
            key = cv2.waitKey(1) & 0xFF
            if key == ord('s'):
                filename = os.path.join(save_dir, f"frame_{int(time.time())}.jpg")
                cv2.imwrite(filename, frame)
                count += 1
                print(f"Manually saved: {filename}")

        # --- Common exit ---
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    print(f"\nCapture stopped. Total saved: {count}")
    cap.release()
    cv2.destroyAllWindows()
