"""
main_capture.py
Entry point to start camera capture from IP Webcam.
"""

from capture.ipcam_capture import start_ipcam_capture

if __name__ == "__main__":
    ip = input("Enter your phone IP (e.g., 192.168.1.5): ")
    start_ipcam_capture(ip)
