import contextvars
import json
from datetime import datetime
from typing import Optional, Any

# Context variable to hold the requestId, accessible throughout the call stack
REQUEST_ID_CTX: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "request_id", default=None
)


def get_request_id() -> Optional[str]:
    """Retrieves the current request ID from context."""
    return REQUEST_ID_CTX.get()


def audit_log(**kwargs: Any) -> None:
    """Prints a structured log line to stdout."""

    log_entry = {
        "requestId": get_request_id() or kwargs.pop("request_id", "N/A"),
        "timestamp": datetime.now().isoformat(),
    }
    log_entry.update(kwargs)
    print(json.dumps(log_entry))
