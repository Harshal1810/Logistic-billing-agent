import json
import logging
from datetime import datetime
from typing import Any


logger = logging.getLogger("app.agent")
if not logger.handlers:
    handler = logging.StreamHandler()
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


def log_event(event: str, **fields: Any) -> None:
    payload = {
        "ts": datetime.utcnow().isoformat(),
        "event": event,
        **fields,
    }
    logger.info(json.dumps(payload, default=str))
