"""Enable repository-relative imports without starting a capture or process."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
for folder in (ROOT, ROOT / 'mcp-server', ROOT / 'tests', ROOT / 'tools/research'):
    value = str(folder)
    if value not in sys.path:
        sys.path.insert(0, value)
