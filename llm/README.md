# Language Model Training from Scratch

This project contains the environment and structure for training a language model from scratch using PyTorch and Hugging Face libraries.

## Project Structure

```
llm_n/
├── data/           # Training and validation datasets
├── models/         # Saved model checkpoints
├── scripts/        # Training and utility scripts
│   └── verify_cuda.py  # GPU and CUDA verification script
├── venv/           # Python virtual environment
├── requirements.txt    # Python dependencies
└── README.md       # This file
```

## Setup Instructions

### 1. Activate Virtual Environment

```powershell
# Windows PowerShell
.\venv\Scripts\activate

# Or use full path
cd llm_n
.\venv\Scripts\activate
```

### 2. Install Dependencies

Due to disk space constraints, you may need to install packages in stages:

#### Option A: Install PyTorch with CUDA support (Requires ~2.5 GB)
```powershell
# For CUDA 12.1
pip install torch --index-url https://download.pytorch.org/whl/cu121

# For CUDA 11.8
pip install torch --index-url https://download.pytorch.org/whl/cu118
```

#### Option B: Install CPU-only PyTorch first (Smaller, ~200 MB)
```powershell
pip install torch
```

#### Install remaining packages:
```powershell
pip install transformers datasets tokenizers numpy matplotlib tqdm
```

Or install all at once (if you have enough disk space):
```powershell
pip install -r requirements.txt
```

### 3. Verify CUDA Setup

Run the verification script to check if GPU is properly configured:

```powershell
python scripts\verify_cuda.py
```

This will check:
- PyTorch installation
- CUDA availability
- GPU detection and properties
- GPU computation test
- Other required libraries

## Upgrading to CUDA Version

If you installed CPU-only PyTorch and want to upgrade to CUDA:

```powershell
# Uninstall CPU version
pip uninstall torch

# Install CUDA version
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

## System Requirements

- **GPU**: NVIDIA GPU with CUDA support
- **CUDA**: Version 11.8 or 12.1 recommended
- **Disk Space**: ~3-4 GB for all dependencies
- **RAM**: 8 GB minimum, 16 GB+ recommended for training
- **Python**: 3.8 or higher

## Disk Space Management

If you encounter "No space left on device" errors:

1. Clean pip cache: `pip cache purge`
2. Free up disk space
3. Install packages one at a time
4. Consider using CPU-only version initially

## Next Steps

1. Prepare your training data in the `data/` folder
2. Create training scripts in the `scripts/` folder
3. Configure model architecture and hyperparameters
4. Start training and save checkpoints to `models/`

## Troubleshooting

### CUDA Not Detected

1. Verify NVIDIA drivers are installed: `nvidia-smi`
2. Check CUDA toolkit installation
3. Ensure PyTorch CUDA version matches your CUDA installation
4. Run `python scripts\verify_cuda.py` for detailed diagnostics

### Import Errors

Make sure virtual environment is activated:
```powershell
.\venv\Scripts\activate
```

### Disk Space Issues

- Use CPU-only PyTorch initially
- Clean temporary files and caches
- Install packages incrementally
