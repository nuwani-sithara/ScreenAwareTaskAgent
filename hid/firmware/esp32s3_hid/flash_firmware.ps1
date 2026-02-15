# Flash ESP32-S3 HID firmware using arduino-cli
# Requirements: Install arduino-cli and add to PATH. Configure board manager for esp32-s3.
# Usage: .\flash_firmware.ps1 -Port COM3
param(
    [string]$Port = "COM3",
    [string]$Board = "esp32:esp32s3:esp32s3",
    [string]$Sketch = "esp32s3_hid.ino"
)

Write-Host "Flashing $Sketch to $Port (board: $Board)"
# Compile
arduino-cli compile --fqbn $Board $PWD\$Sketch
if ($LASTEXITCODE -ne 0) { Write-Error "Compile failed"; exit 1 }
# Upload
arduino-cli upload -p $Port --fqbn $Board $PWD\$Sketch
if ($LASTEXITCODE -ne 0) { Write-Error "Upload failed"; exit 1 }
Write-Host "Upload finished. Serial monitor will show device output at 115200."