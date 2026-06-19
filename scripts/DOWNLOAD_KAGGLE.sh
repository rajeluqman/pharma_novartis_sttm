#!/bin/bash
# Download Kaggle dataset
# Usage: bash scripts/download_dataset.sh

set -e

DATASET_SLUG="<INSERT_SLUG_HERE>"  # e.g. "olistbr/brazilian-ecommerce"
DOWNLOAD_DIR="data/raw"

# Verify Kaggle credentials
if [ ! -f ~/.kaggle/kaggle.json ]; then
    echo "❌ ~/.kaggle/kaggle.json not found"
    echo "Get API key from: https://www.kaggle.com/settings → API → Create New Token"
    echo "Then: mkdir -p ~/.kaggle && cp kaggle.json ~/.kaggle/ && chmod 600 ~/.kaggle/kaggle.json"
    exit 1
fi

# Verify Kaggle CLI installed
if ! command -v kaggle &> /dev/null; then
    pip install kaggle
fi

# Download
mkdir -p $DOWNLOAD_DIR
kaggle datasets download -d $DATASET_SLUG -p $DOWNLOAD_DIR --unzip

echo "✅ Dataset downloaded to $DOWNLOAD_DIR/"
ls -lh $DOWNLOAD_DIR/
