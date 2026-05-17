"""
Pytest configuration and fixtures
"""
import sys
from pathlib import Path

# Add backend directory to Python path so imports work correctly
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))
