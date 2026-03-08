import os
import json
import logging
from datetime import datetime

BASE_OUTPUT_DIR = "agent_outputs"

def create_run_folder():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_folder = os.path.join(BASE_OUTPUT_DIR, f"run_{timestamp}")

    os.makedirs(run_folder, exist_ok=True)

    return run_folder


def save_json(data, filename, run_folder):
    try:
        file_path = os.path.join(run_folder, f"{filename}.json")

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        logging.info(f"💾 Saved {filename} → {file_path}")

    except Exception as e:
        logging.error(f"❌ Failed to save {filename}: {e}")