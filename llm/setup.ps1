# Setup Script for Windows - Language Model Training Environment
# Run this script to complete the setup

Write-Host "="*70 -ForegroundColor Cyan
Write-Host "Language Model Training Environment Setup" -ForegroundColor Cyan
Write-Host "="*70 -ForegroundColor Cyan

# Step 1: Check if Virtual Environment exists
Write-Host "`n[1/5] Checking virtual environment..." -ForegroundColor Yellow
if (Test-Path ".\venv\Scripts\python.exe") {
    Write-Host "✓ Virtual environment found" -ForegroundColor Green
} else {
    Write-Host "✗ Virtual environment not found. Creating..." -ForegroundColor Red
    python -m venv venv
    Write-Host "✓ Virtual environment created" -ForegroundColor Green
}

# Step 2: Check Visual C++ Redistributable
Write-Host "`n[2/5] Checking Visual C++ Redistributable..." -ForegroundColor Yellow
Write-Host "This is required for PyTorch to work on Windows" -ForegroundColor Gray

$vcRedistPath = "C:\Program Files\Microsoft Visual Studio\*\VC\Redist\MSVC\*\x64\Microsoft.VC*.CRT"
if (Test-Path $vcRedistPath) {
    Write-Host "✓ Visual C++ Redistributable appears to be installed" -ForegroundColor Green
} else {
    Write-Host "⚠ Visual C++ Redistributable may not be installed" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Please download and install from:" -ForegroundColor Yellow
    Write-Host "https://aka.ms/vs/17/release/vc_redist.x64.exe" -ForegroundColor Cyan
    Write-Host ""
    $response = Read-Host "Open download page in browser? (y/n)"
    if ($response -eq 'y') {
        Start-Process "https://aka.ms/vs/17/release/vc_redist.x64.exe"
        Write-Host "After installing, press Enter to continue..."
        Read-Host
    }
}

# Step 3: Check NVIDIA GPU
Write-Host "`n[3/5] Checking for NVIDIA GPU..." -ForegroundColor Yellow
try {
    $nvidiaCheck = nvidia-smi 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ NVIDIA GPU detected!" -ForegroundColor Green
        nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | ForEach-Object {
            Write-Host "  $_" -ForegroundColor Gray
        }
        $hasGPU = $true
    } else {
        Write-Host "⚠ nvidia-smi not found or no GPU detected" -ForegroundColor Yellow
        $hasGPU = $false
    }
} catch {
    Write-Host "⚠ No NVIDIA GPU detected" -ForegroundColor Yellow
    $hasGPU = $false
}

# Step 4: Check disk space
Write-Host "`n[4/5] Checking disk space..." -ForegroundColor Yellow
$drive = (Get-Location).Drive.Name
$disk = Get-PSDrive $drive
$freeSpaceGB = [math]::Round($disk.Free / 1GB, 2)
Write-Host "Free space on ${drive}: drive: $freeSpaceGB GB" -ForegroundColor Gray

if ($freeSpaceGB -lt 3) {
    Write-Host "⚠ Low disk space! CUDA PyTorch requires ~2.5 GB" -ForegroundColor Yellow
    Write-Host "Current setup uses CPU-only PyTorch (~111 MB)" -ForegroundColor Gray
    $useCPU = $true
} else {
    Write-Host "✓ Sufficient disk space available" -ForegroundColor Green
    $useCPU = $false
}

# Step 5: Offer to install/upgrade PyTorch
Write-Host "`n[5/5] PyTorch Installation" -ForegroundColor Yellow

if ($hasGPU -and -not $useCPU) {
    Write-Host ""
    Write-Host "You have an NVIDIA GPU and sufficient disk space." -ForegroundColor Green
    Write-Host "Would you like to install PyTorch with CUDA support?" -ForegroundColor Yellow
    Write-Host "  [1] Install CUDA 12.1 version (Recommended, ~2.5 GB)" -ForegroundColor Gray
    Write-Host "  [2] Install CUDA 11.8 version (~2.5 GB)" -ForegroundColor Gray
    Write-Host "  [3] Keep CPU-only version (Already installed)" -ForegroundColor Gray
    Write-Host "  [4] Skip" -ForegroundColor Gray
    
    $choice = Read-Host "Enter choice (1-4)"
    
    switch ($choice) {
        "1" {
            Write-Host "Installing PyTorch with CUDA 12.1..." -ForegroundColor Yellow
            .\venv\Scripts\python.exe -m pip uninstall torch -y
            .\venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cu121
        }
        "2" {
            Write-Host "Installing PyTorch with CUDA 11.8..." -ForegroundColor Yellow
            .\venv\Scripts\python.exe -m pip uninstall torch -y
            .\venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cu118
        }
        "3" {
            Write-Host "Keeping CPU-only PyTorch" -ForegroundColor Gray
        }
        default {
            Write-Host "Skipped" -ForegroundColor Gray
        }
    }
} else {
    Write-Host "CPU-only PyTorch is installed (suitable for development and small models)" -ForegroundColor Gray
}

# Final verification
Write-Host "`n"
Write-Host "="*70 -ForegroundColor Cyan
Write-Host "Running verification..." -ForegroundColor Cyan
Write-Host "="*70 -ForegroundColor Cyan

.\venv\Scripts\python.exe scripts\quick_test.py

Write-Host "`n"
Write-Host "="*70 -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "="*70 -ForegroundColor Cyan
Write-Host ""
Write-Host "To activate the environment:" -ForegroundColor Yellow
Write-Host "  .\venv\Scripts\activate" -ForegroundColor Cyan
Write-Host ""
Write-Host "Useful commands:" -ForegroundColor Yellow
Write-Host "  python scripts\quick_test.py          - Test installation" -ForegroundColor Gray
Write-Host "  python scripts\verify_cuda.py         - Detailed CUDA check" -ForegroundColor Gray
Write-Host "  pip list                              - List installed packages" -ForegroundColor Gray
Write-Host ""
Write-Host "Documentation:" -ForegroundColor Yellow
Write-Host "  README.md               - Project overview and setup guide" -ForegroundColor Gray
Write-Host "  TROUBLESHOOTING.md      - Common issues and solutions" -ForegroundColor Gray
Write-Host ""
