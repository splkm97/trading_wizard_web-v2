"""Pytest configuration for backend tests.

Sets up the Python path to allow imports like:
- backend.src.api.daily_focus.recommendations
- backend.src.services.signal_scanner
"""

import sys
from pathlib import Path

# Add the project root (parent of backend/) to sys.path
# This allows imports like `from backend.src.xxx import yyy`
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
