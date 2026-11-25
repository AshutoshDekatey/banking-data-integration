import json
import sys
from datetime import datetime, timezone


def log(event: str, **fields: object) -> None:
    print(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(),
                      "event": event, **fields}, default=str), file=sys.stderr, flush=True)
