from capture.ipcam_capture import start_capture

if __name__ == "__main__":
    ip = input("Enter your phone IP (e.g., 192.168.1.5): ")
    mode = input("Enter mode (auto / selective): ").strip().lower() or "auto"
    interval = input("Enter capture interval (default 1 sec): ")
    interval = float(interval) if interval.strip() else 1.0

    start_capture(ip, mode=mode, interval=interval)
