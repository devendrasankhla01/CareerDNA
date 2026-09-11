import os
import sys
from pathlib import Path

# Add backend directory to sys.path so app modules are discovered
BASE_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BASE_DIR))

from app.main import app
