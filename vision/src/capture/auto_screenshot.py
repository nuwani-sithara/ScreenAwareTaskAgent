import pyautogui
import time
import os
from datetime import datetime

SAVE_DIR = "data/dataset/raw"

if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

print("📸 Auto Screenshot Started...")
print("Go to https://play2048.co/ and keep the window visible.")
print("Press CTRL + C to stop.\n")

while True:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filepath = os.path.join(SAVE_DIR, f"screenshot_{timestamp}.png")

    # Take full-screen screenshot
    screenshot = pyautogui.screenshot()

    # OPTIONAL: Crop the screenshot to game area
    # If game starts at x=400, y=100 → adjust based on your screen
    # screenshot = screenshot.crop((400, 100, 1000, 700))

    screenshot.save(filepath)
    print(f"Saved: {filepath}")

    time.sleep(1)  # capture every 1 second
