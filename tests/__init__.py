import sys
from pathlib import Path

_sync_dir = Path(__file__).resolve().parent.parent / "sync"
if str(_sync_dir) not in sys.path:
    sys.path.insert(0, str(_sync_dir))
