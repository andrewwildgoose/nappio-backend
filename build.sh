#!/bin/bash
set -e

echo "Python version:"
python --version

echo "Installing dependencies..."
python -m pip install --upgrade pip
pip install -r requirements.txt

echo "Installed packages:"
pip list