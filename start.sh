#!/bin/bash
echo "=================================================="
echo "🚀 Hudhud Bot Starting via start.sh..."
echo "=================================================="
echo "PORT: $PORT"
echo "Python version: $(python --version)"
echo "Starting uvicorn..."
exec python -u main.py
