#!/usr/bin/env python
"""
validate_watcher.py - Watches last_instruction.txt and auto-validates new instructions
Usage: python validate_watcher.py

This script monitors `last_instruction.txt` in the llm folder. Whenever the file
is updated, it calls `validate_from_demo.validate_and_display()` to show validation.
"""
import time
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from validate_from_demo import validate_and_display

WATCH_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "last_instruction.txt")

def watch_loop(poll_interval=1.0):
    last_mtime = 0
    last_value = None
    print("Watching for new instructions in:", WATCH_FILE)
    try:
        while True:
            try:
                if os.path.exists(WATCH_FILE):
                    mtime = os.path.getmtime(WATCH_FILE)
                    if mtime != last_mtime:
                        last_mtime = mtime
                        with open(WATCH_FILE, "r", encoding="utf-8") as f:
                            value = f.read().strip()
                        if value and value != last_value:
                            print(f"\nDetected new instruction: {value}\n")
                            last_value = value
                            # Validate
                            validate_and_display(value)
            except Exception as e:
                print("Watcher error:", e)
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        print('\nWatcher stopped by user')

if __name__ == '__main__':
    watch_loop()
