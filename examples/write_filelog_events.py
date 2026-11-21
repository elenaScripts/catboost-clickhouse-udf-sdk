"""Append synthetic JSONEachRow events to a FileLog demo file."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


# These values demonstrate the UDF interface, not real incident probabilities.
SAMPLES = (
    ("checkout", "200", 180, 0),
    ("checkout", "500", 1600, 2),
    ("billing", "503", 2400, 3),
    ("search", "200", 95, 0),
    ("recommendations", "429", 750, 1),
    ("checkout", "502", 3100, 2),
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Path to the existing demo .log file")
    args = parser.parse_args()
    if not args.path.is_file():
        parser.error("create the demo .log file before appending events")

    with args.path.open("a", encoding="utf-8") as stream:
        for service, error_code, response_ms, retry_count in SAMPLES:
            event = {
                "event_time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                "event_id": str(uuid4()),
                "service": service,
                "error_code": error_code,
                "response_ms": response_ms,
                "retry_count": retry_count,
            }
            stream.write(json.dumps(event, separators=(",", ":")) + "\n")
    print(f"Appended {len(SAMPLES)} synthetic events to {args.path}")


if __name__ == "__main__":
    main()
