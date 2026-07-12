#!/usr/bin/env bash
set -euo pipefail

# Build frontend static assets
cd frontend
npm ci
npm run build
cd ..

# Install backend Python dependencies
cd backend
pip install uv
uv sync --frozen
