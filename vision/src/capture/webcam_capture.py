import cv2
import os
import time
import platform

def _gui_available():
    """
    Check whether OpenCV highgui window functions are available.
    Returns False for headless builds.
    """
    try:
        test = cv2.imread("debug_ocr_input.png")
        if test is None:
            # tiny dummy image if file not present
            import numpy as np
            test = np.zeros((2, 2, 3), dtype=np.uint8)
        cv2.imshow("cv2_gui_test", test)
        cv2.waitKey(1)
        cv2.destroyWindow("cv2_gui_test")
        return True
    except Exception:
        return False

def list_available_cameras(max_index=5):
    """
    Returns a list of available camera indexes and shows a brief preview.
    """
    available_cameras = []
    print("Scanning for available cameras...")

    backend = cv2.CAP_DSHOW if platform.system() == "Windows" else 0

    gui_ok = _gui_available()

    for i in range(max_index):
        cap = cv2.VideoCapture(i, backend)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                available_cameras.append(i)
                print(f"Camera index {i} is available")
                if gui_ok:
                    cv2.imshow(f"Preview Camera {i}", frame)
                    cv2.waitKey(1000)  # show preview for 1 second
                    cv2.destroyWindow(f"Preview Camera {i}")
            cap.release()
        else:
            print(f"Camera index {i} not available")
    return available_cameras

def select_camera(available_cameras):
    """
    Prompts the user to select a camera from the available list.
    """
    print("\nSelect the camera you want to use:")
    for idx, cam in enumerate(available_cameras):
        print(f"{idx}: Camera index {cam}")
    while True:
        try:
            choice = int(input("Enter the number corresponding to the camera: "))
            if 0 <= choice < len(available_cameras):
                return available_cameras[choice]
            else:
                print("Invalid choice. Try again.")
        except ValueError:
            print("Please enter a valid number.")

def start_webcam_capture(camera_index=None, save_dir="data/raw_frames", mode="auto", interval=1):
    os.makedirs(save_dir, exist_ok=True)
    gui_ok = _gui_available()

    # Auto-select camera if index not provided
    if camera_index is None:
        available_cameras = list_available_cameras()
        if not available_cameras:
            print("No cameras found.")
            return
        camera_index = select_camera(available_cameras)

    backend = cv2.CAP_DSHOW if platform.system() == "Windows" else 0
    cap = cv2.VideoCapture(camera_index, backend)

    if not cap.isOpened():
        print(f"Unable to open camera index {camera_index}")
        return

    print(f"\nWebcam Connected (Camera Index: {camera_index})")
    print(f"Mode: {mode.upper()} | Interval: {interval}s")
    if gui_ok:
        print("Press 'q' to stop.\n")
    else:
        print("GUI preview disabled (headless OpenCV). Use Ctrl+C to stop.\n")

    last_saved = 0
    count = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Failed to read frame. Retrying...")
                time.sleep(0.2)
                continue

            if gui_ok:
                cv2.imshow("Camera Capture", frame)

            # AUTO MODE
            if mode == "auto":
                now = time.time()
                if now - last_saved >= interval:
                    filename = os.path.join(save_dir, f"frame_{int(now)}.jpg")
                    cv2.imwrite(filename, frame)
                    last_saved = now
                    count += 1
                    print(f"Saved: {filename}")

            # SELECTIVE MODE
            if mode == "selective":
                if gui_ok:
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('s'):
                        filename = os.path.join(save_dir, f"frame_{int(time.time())}.jpg")
                        cv2.imwrite(filename, frame)
                        count += 1
                        print(f"Manually saved: {filename}")
                else:
                    print("Selective mode requires GUI preview. Use mode='auto' in headless OpenCV.")
                    break

            # EXIT
            if gui_ok and (cv2.waitKey(1) & 0xFF == ord('q')):
                break

    except KeyboardInterrupt:
        print("\nCapture interrupted by user.")

    print(f"\nCapture stopped. Total saved: {count}")
    cap.release()
    if gui_ok:
        cv2.destroyAllWindows()

def start_webcam_stream(camera_index=0, width: int | None = None, height: int | None = None):
    """
    Generator-style webcam stream for Vision API.
    Returns frames continuously until stopped.
    """
    backend = cv2.CAP_DSHOW if platform.system() == "Windows" else 0
    cap = cv2.VideoCapture(camera_index, backend)

    # If a desired frame size is provided, attempt to set it on the capture.
    # Some cameras/drivers may not honor these values but OpenCV will try.
    if width is not None:
        try:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(width))
        except Exception:
            pass
    if height is not None:
        try:
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(height))
        except Exception:
            pass
    else:
        # No explicit request: attempt to probe and, if the camera reports a
        # small default (commonly 640x480), try a list of preferred larger
        # resolutions and pick the best one accepted by the driver.
        try:
            cur_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            cur_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            if max(cur_w, cur_h) <= 640:
                preferred = [(1920, 1080), (1280, 720), (1600, 1200), (1024, 768)]
                for pw, ph in preferred:
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(pw))
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(ph))
                    # re-query
                    rw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
                    rh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
                    if rw >= pw - 16 and rh >= ph - 16:
                        # driver honored size (allow small delta)
                        break
        except Exception:
            pass

    if not cap.isOpened():
        raise RuntimeError(f"Unable to open camera index {camera_index}")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                continue
            yield frame
    finally:
        cap.release()

if __name__ == "__main__":
    start_webcam_capture()

