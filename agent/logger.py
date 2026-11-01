import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .config import MODEL

RUN_ID = uuid.uuid4().hex
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{RUN_ID[:8]}.jsonl"


def log(event, **fields):
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "run_id": RUN_ID,
        "event": event,
        "model": MODEL,
        **fields,
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def elapsed_ms(start):
    return round((time.perf_counter() - start) * 1000)
