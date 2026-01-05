# src/preprocessing/main_capture.py
"""
Orchestrator: capture -> preprocess
Usage:
    python src/preprocessing/main_capture.py
"""
import os
import subprocess

# Adjust commands/params as needed
CAPTURE_CMD = "python src/capture/game_capture.py --interval 1 --limit 200"
PREPROCESS_CMD = "python src/preprocessing/preprocess.py --resize 640"

def run_cmd(cmd):
    print("Running:", cmd)
    code = os.system(cmd)
    if code != 0:
        print("Command failed:", cmd)
        raise SystemExit(code)

if __name__ == "__main__":
    run_cmd(CAPTURE_CMD)
    run_cmd(PREPROCESS_CMD)
    print("Capture + Preprocess complete.")
