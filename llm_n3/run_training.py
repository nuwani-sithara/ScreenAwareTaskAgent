"""
Run training in background with proper logging
"""
import subprocess
import sys
from pathlib import Path

script_dir = Path(__file__).parent
train_script = script_dir / "scripts" / "train_automation.py"
output_log = script_dir / "training_output.log"
error_log = script_dir / "training_error.log"

print("Starting training in background...")
print(f"Output log: {output_log}")
print(f"Error log: {error_log}")
print()

# Start training process
with open(output_log, 'w', encoding='utf-8') as out_f, open(error_log, 'w', encoding='utf-8') as err_f:
    process = subprocess.Popen(
        [sys.executable, str(train_script)],
        stdout=out_f,
        stderr=err_f,
        cwd=str(script_dir)
    )
    
    print(f"Training started with PID: {process.pid}")
    print()
    print("To check progress:")
    print(f"  Get-Content '{output_log}' -Tail 50 -Wait")
    print()
    print("To check if running:")
    print(f"  Get-Process -Id {process.pid} -ErrorAction SilentlyContinue")
    print()
    print("To stop training:")
    print(f"  Stop-Process -Id {process.pid}")
