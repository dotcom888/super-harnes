# -*- coding: utf-8 -*-
"""
Super-Harnes Backend Core Package
"""
import sys
from pathlib import Path

_backend_dir = Path(__file__).resolve().parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))