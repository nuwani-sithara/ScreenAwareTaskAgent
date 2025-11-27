<# PowerShell setup script for Windows (use conda recommended for faiss) #>
param(
    [string] $envName = "llm-env",
    [switch] $useConda
)

if ($useConda -or (Get-Command conda -ErrorAction SilentlyContinue)) {
    Write-Host "Creating conda environment: $envName"
    conda create -n $envName python=3.10 -y
    conda activate $envName
    conda install -c conda-forge numpy=1.25.11 -y
    conda install -c conda-forge faiss-cpu -y

    pip install --upgrade pip
    pip install -r requirements.txt
    Write-Host "Conda setup complete. Activate with 'conda activate $envName'"
    exit 0
} else {
    Write-Host "Conda not found — using venv + pip (FAISS on Windows is best via conda)"
    $venvDir = ".venv"
    python -m venv $venvDir
    .\$venvDir\Scripts\Activate.ps1
    pip install --upgrade pip
    pip install -r requirements.txt
    Write-Host "venv created. Activate with '.\$venvDir\Scripts\Activate.ps1'"
}

# verify installation
python -c "import numpy as np, sys; print('Python:', sys.executable); print('numpy', np.__version__)"
python -c "import sentence_transformers; import sklearn; print('sentence-transformers', sentence_transformers.__version__); print('sklearn', sklearn.__version__)"
python -c "import safetensors; print('safetensors', safetensors.__version__)"
