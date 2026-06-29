"""Wide structured events: one JSON line per unit of work.

The point is to read an incident (or a beat, or an action) end to end from a
single line, instead of grepping and stitching a dozen low-context lines back
together. No PII — reference a person by user UUID only (see issue #54).

ponytail: a JSON line to the stdlib logger covers it; reach for structlog only
if request-scoped context binding across many call sites is ever wanted.
"""

import json
import logging
from datetime import datetime

logger = logging.getLogger("oncall.events")


def log_event(event: str, **fields) -> None:
    payload = {"event": event, "ts": datetime.utcnow().isoformat() + "Z"}
    # Drop None so the line carries only what actually happened.
    payload.update({k: v for k, v in fields.items() if v is not None})
    logger.info(json.dumps(payload, default=str, sort_keys=True))
