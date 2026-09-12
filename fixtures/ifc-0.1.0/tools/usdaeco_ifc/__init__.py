"""IFC converter and native host integration."""
__version__ = "0.1.0"

import os
from pathlib import Path
import sys
_core = Path(os.environ.get('AECO_CORE_ROOT', Path(__file__).resolve().parents[3] / 'usdaeco-core'))
if (_core / 'tools/usdaeco_tools').is_dir():
    sys.path.insert(0, str(_core / 'tools'))
