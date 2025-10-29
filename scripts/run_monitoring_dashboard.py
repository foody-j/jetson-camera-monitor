#!/usr/bin/env python3
"""
Run Monitoring Dashboard

Entry point script to launch the centralized monitoring dashboard.

Usage:
    python scripts/run_monitoring_dashboard.py

    Or make it executable and run directly:
    chmod +x scripts/run_monitoring_dashboard.py
    ./scripts/run_monitoring_dashboard.py
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

# Import and run main app
from gui.main_app import main

if __name__ == '__main__':
    print("=" * 60)
    print("🤖 Frying AI Monitoring System")
    print("=" * 60)
    print()
    print("Starting centralized monitoring dashboard...")
    print("Access the dashboard at: http://localhost:5000")
    print()
    print("Features:")
    print("  ✓ Camera Monitoring")
    print("  ✓ Vibration Detection (RS485)")
    print("  ✓ Frying AI Analysis")
    print("  ✓ Automatic Work Scheduler (8:30 AM - 7:00 PM)")
    print()
    print("Press Ctrl+C to stop")
    print("=" * 60)
    print()

    try:
        main()
    except KeyboardInterrupt:
        print("\n\nShutdown requested. Goodbye!")
        sys.exit(0)
