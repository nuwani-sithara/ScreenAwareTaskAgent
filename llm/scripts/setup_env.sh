#!/usr/bin/env bash
# Setup script (Linux / macOS) for the llm demo project
set -e
ENV_DIR=".venv"
PYTHON=${PYTHON:-python3}

echo "Creating venv at: $ENV_DIR"
$PYTHON -m venv $ENV_DIR
source $ENV_DIR/bin/activate

pip install -U pip
# Install pinned packages from requirements.txt
if [ -f "requirements.txt" ]; then
  echo "Installing from requirements.txt..."
  pip install -r requirements.txt
else
  echo "requirements.txt not found: installing minimal dependencies..."
  pip install "numpy<2" sentence-transformers transformers scikit-learn sprocket safetensors
fi

# Install faiss via pip if available (Linux / macOS) — on Windows prefer conda for faiss.
pip install faiss-cpu || echo "faiss-cpu pip install failed. For full faiss support, install via conda: 'conda install -c conda-forge faiss-cpu'"

# Verification
python -c "import numpy as np, sys; print('Python:', sys.executable); print('numpy', np.__version__)"
python -c "import sentence_transformers; import sklearn; print('sentence-transformers', sentence_transformers.__version__); print('sklearn', sklearn.__version__)"
python -c "import safetensors; print('safetensors', safetensors.__version__)"

echo "Setup complete. Activate the env with: source $ENV_DIR/bin/activate"
