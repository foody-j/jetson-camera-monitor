#!/usr/bin/env python3
"""
Run Dash Monitoring Dashboard

Entry point script to launch the beautiful Dash-based monitoring dashboard.

Usage:
    python scripts/run_dash_dashboard.py

    Or make it executable and run directly:
    chmod +x scripts/run_dash_dashboard.py
    ./scripts/run_dash_dashboard.py
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

# Import and run main app
from gui.dash_app import main

if __name__ == '__main__':
    main()
