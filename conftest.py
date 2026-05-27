"""
conftest.py — pytest configuration for the SC Decision Engine assessment.

Adds the repository root to sys.path so that top-level packages
(agent, tools, utils, models) are importable from any test file.
"""

import sys
import os

# Ensure the repo root is on the path regardless of where pytest is invoked from.
sys.path.insert(0, os.path.dirname(__file__))
