"""Exercise source packages without an editable install or setuptools."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "src"), str(ROOT)]
