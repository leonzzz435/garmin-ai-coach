#!/bin/bash
# Pixi environment setup script for tele_garmin

echo "🚀 Setting up tele_garmin environment..."

# Set environment variables for development
export PYTHONPATH="${PIXI_PROJECT_ROOT}:${PYTHONPATH}"
export ENVIRONMENT="${ENVIRONMENT:-development}"

# Create necessary directories
mkdir -p logs
mkdir -p data/plots
mkdir -p data/cache
mkdir -p agents_docs

echo "✅ Environment setup complete!"
echo "📁 Project root: ${PIXI_PROJECT_ROOT}"
echo "🐍 Python path: ${PYTHONPATH}"
echo "🔧 Environment: ${ENVIRONMENT}"