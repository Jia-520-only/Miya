#!/bin/bash

# MIYA - Multi-Terminal Mode

echo "========================================"
echo "  MIYA - Multi-Terminal Mode"
echo "========================================"
echo ""
echo "[Starting] Miya Multi-Terminal System..."
echo ""

# Check virtual environment
if [ ! -d "venv" ]; then
    echo "[ERROR] Virtual environment not found"
    echo "Please run install.sh first"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Start multi-terminal system
echo "[Info] Launching multi-terminal shell..."
echo ""
python run/multi_terminal_main.py
