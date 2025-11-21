#!/bin/bash
# Render build script (optional - Render auto-detects Python projects)
# This script runs before the service starts

echo "Building Star4ce backend..."

# Install dependencies
pip install -r requirements.txt

# Run database migrations (if needed)
# python3 migrate_subscription_columns.py

echo "Build complete!"

