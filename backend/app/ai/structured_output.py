import json
import re
from typing import Any


JSON_FENCE_PATTERN = re.compile(
    r"\A\s*\x60\x60\x60(?:json)?\s*(.*?)\s*\x60\x60\x60\s*\Z",
    flags=re.IGNORECASE | re.DOTALL,
)


def load_json_output(raw: str) -> Any:
    """Load bare JSON or one full-response JSON code fence.

    Surrounding prose and partial JSON extraction remain unsupported so model
    output continues to fail closed.
    """

    try:
        return json.loads(raw)
    except json.JSONDecodeError as bare_error:
        match = JSON_FENCE_PATTERN.fullmatch(raw)
        if match is None:
            raise bare_error
        return json.loads(match.group(1))


__all__ = ["load_json_output"]
