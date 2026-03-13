from __future__ import annotations

import json
from typing import Any


def estimate_json_bytes(payload: Any) -> int:
    try:
        return len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    except TypeError:
        return len(repr(payload).encode("utf-8"))
