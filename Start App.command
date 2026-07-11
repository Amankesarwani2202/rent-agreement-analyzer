#!/bin/bash
# Double-click this file to start the Rent Agreement Analyzer website.
cd "$(dirname "$0")"

echo "=============================================="
echo "  Rent Agreement Analyzer - starting up..."
echo "  (first run installs a few things: 2-5 min)"
echo "=============================================="

# Find Python
if command -v python3 >/dev/null 2>&1; then
    PY=python3
else
    echo ""
    echo "Python is not installed yet."
    echo "A popup should appear - click 'Install' and run this file again after it finishes."
    xcode-select --install 2>/dev/null
    read -n 1 -s -r -p "Press any key to close..."
    exit 1
fi

# Install what the app needs (only slow the first time)
$PY -m pip install --quiet --user streamlit pypdf 2>/dev/null || $PY -m pip install --quiet streamlit pypdf

echo ""
echo "Opening the website in your browser..."
echo "(Keep this window open while using the app. Close it to stop.)"
echo ""

$PY -m streamlit run app.py
