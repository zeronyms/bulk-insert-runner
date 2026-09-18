#!/usr/bin/env bash

# Ensure script runs from its own directory
cd "$(dirname "$0")"

VENV_DIR=".venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "[SETUP] Setting up Python Virtual Environment..."
    python3 -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to create venv. Make sure python3-venv is installed."
        exit 1
    fi
fi

if [ -f "requirements.txt" ]; then
    "$VENV_DIR/bin/pip" install -q --upgrade pip
    "$VENV_DIR/bin/pip" install -q -r requirements.txt
elif [ -f "requirement.txt" ]; then
    "$VENV_DIR/bin/pip" install -q --upgrade pip
    "$VENV_DIR/bin/pip" install -q -r requirement.txt
fi

"$VENV_DIR/bin/python" universal_bulk.py
