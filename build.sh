#!/usr/bin/env bash
# exit on error
set -o errexit

# Install system dependencies (ffmpeg)
# Render provides ffmpeg in their environment, so we don't need to install it
# Just verify it's available
if ! command -v ffmpeg &> /dev/null; then
    echo "ffmpeg is not available. Please contact Render support."
    exit 1
fi

# Install Python dependencies
pip install -r requirements.txt 