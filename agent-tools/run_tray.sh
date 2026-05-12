#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
python usage-checker/claude_usage.py --tray
