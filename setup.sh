#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

echo "--- Starting RVC Fork Dependency Installation ---"

# --- 2. Install Other Requirements ---
echo "Installing requirements from rvc-requirements.txt..."
python -m pip install pip==23.3.2
pip install -r requirements/RVC/reclists-RVC/rvc-requirements.txt

pip uninstall torch torchvision torchaudio

# --- 1. Install PyTorch with the Correct CUDA Version ---
echo "Detecting CUDA version..."

# Detect CUDA version from nvidia-smi, fallback to nvcc if not available
if command -v nvidia-smi &> /dev/null && nvidia-smi -q &> /dev/null; then
    CUDA_VERSION=$(nvidia-smi -q | grep "CUDA Version" | awk '{print $NF}' | cut -d'.' -f1,2)
else
    # Fallback to nvcc if nvidia-smi is not conclusive
    CUDA_VERSION=$(nvcc --version | grep -o 'release [0-9]\+\.[0-9]\+' | grep -o '[0-9]\+\.[0-9]\+')
fi

echo "Detected CUDA Version: $CUDA_VERSION"

# Map CUDA version to PyTorch pip install format (e.g., cu118)
CUDA_VERSION_STRING=""
if [[ "$CUDA_VERSION" == "11.8" ]]; then
    CUDA_VERSION_STRING="cu118"
elif [[ "$CUDA_VERSION" == "12.1" ]]; then
    CUDA_VERSION_STRING="cu121"
elif [[ "$CUDA_VERSION" == "12.8" ]]; then
    CUDA_VERSION_STRING="cu128"
# You can add more mappings for other CUDA versions.
# Check the PyTorch website for the correct string: https://pytorch.org/get-started/previous-versions/
else
    echo "Unsupported or undetected CUDA version: $CUDA_VERSION."
    echo "Defaulting to CUDA 11.8 for PyTorch installation."
    CUDA_VERSION_STRING="cu118"
fi

echo "Installing PyTorch for CUDA version string: $CUDA_VERSION_STRING"
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/$CUDA_VERSION_STRING

# --- 3. Download Models ---
echo "Downloading pre-trained models..."
python tools/download_models.py

echo "--- Setup complete! ---"
