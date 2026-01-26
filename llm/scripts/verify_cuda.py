"""
CUDA and GPU Verification Script
This script checks if PyTorch is installed with CUDA support and verifies GPU availability.
"""

import sys

def check_pytorch():
    """Check if PyTorch is installed and display version."""
    try:
        import torch
        print("✓ PyTorch is installed")
        print(f"  Version: {torch.__version__}")
        return torch
    except ImportError:
        print("✗ PyTorch is NOT installed")
        print("  Install with: pip install torch --index-url https://download.pytorch.org/whl/cu121")
        return None

def check_cuda(torch):
    """Check CUDA availability and display GPU information."""
    if torch is None:
        return False
    
    cuda_available = torch.cuda.is_available()
    print(f"\nCUDA Available: {cuda_available}")
    
    if cuda_available:
        print(f"✓ CUDA is available!")
        print(f"  CUDA Version: {torch.version.cuda}")
        print(f"  cuDNN Version: {torch.backends.cudnn.version()}")
        print(f"  Number of GPUs: {torch.cuda.device_count()}")
        
        for i in range(torch.cuda.device_count()):
            print(f"\n  GPU {i}: {torch.cuda.get_device_name(i)}")
            print(f"    Memory Total: {torch.cuda.get_device_properties(i).total_memory / 1024**3:.2f} GB")
            print(f"    Compute Capability: {torch.cuda.get_device_properties(i).major}.{torch.cuda.get_device_properties(i).minor}")
        
        # Test GPU computation
        print("\nTesting GPU computation...")
        try:
            x = torch.randn(1000, 1000).cuda()
            y = torch.randn(1000, 1000).cuda()
            z = torch.matmul(x, y)
            print("✓ GPU computation test passed!")
        except Exception as e:
            print(f"✗ GPU computation test failed: {e}")
            return False
        
        return True
    else:
        print("✗ CUDA is NOT available")
        print("  PyTorch will run on CPU only")
        print("\nPossible reasons:")
        print("  1. PyTorch CPU-only version is installed")
        print("  2. No NVIDIA GPU detected")
        print("  3. CUDA drivers not installed")
        print("\nTo install PyTorch with CUDA support:")
        print("  pip uninstall torch")
        print("  pip install torch --index-url https://download.pytorch.org/whl/cu121")
        return False

def check_other_libraries():
    """Check if other required libraries are installed."""
    libraries = {
        'transformers': 'Hugging Face Transformers',
        'datasets': 'Hugging Face Datasets',
        'tokenizers': 'Tokenizers',
        'numpy': 'NumPy',
        'matplotlib': 'Matplotlib',
        'tqdm': 'tqdm'
    }
    
    print("\n" + "="*60)
    print("Checking other required libraries:")
    print("="*60)
    
    all_installed = True
    for module, name in libraries.items():
        try:
            lib = __import__(module)
            version = getattr(lib, '__version__', 'unknown')
            print(f"✓ {name:30s} {version}")
        except ImportError:
            print(f"✗ {name:30s} NOT INSTALLED")
            all_installed = False
    
    return all_installed

def main():
    """Main verification function."""
    print("="*60)
    print("PyTorch and CUDA Verification")
    print("="*60)
    
    # Check PyTorch
    torch = check_pytorch()
    
    # Check CUDA
    if torch:
        cuda_ok = check_cuda(torch)
    else:
        cuda_ok = False
    
    # Check other libraries
    libs_ok = check_other_libraries()
    
    # Summary
    print("\n" + "="*60)
    print("Summary:")
    print("="*60)
    if torch and cuda_ok and libs_ok:
        print("✓ All systems ready for GPU-accelerated training!")
    elif torch and libs_ok:
        print("⚠ PyTorch installed but CUDA not available (CPU-only mode)")
    else:
        print("✗ Setup incomplete. Please install missing packages.")
        print("\nRun: pip install -r requirements.txt")
        print("For CUDA support: pip install torch --index-url https://download.pytorch.org/whl/cu121")
    
    return 0 if (torch and libs_ok) else 1

if __name__ == "__main__":
    sys.exit(main())
