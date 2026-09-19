import json
import re
import shlex
from typing import Any
from urllib.parse import urlparse


def parse_curl(curl_cmd: str) -> dict[str, Any]:
    """Parse cURL command string copied from browser DevTools.

    Extracts URL, HTTP method, headers, and JSON payload if present.
    """
    try:
        tokens = shlex.split(curl_cmd)
    except ValueError:
        tokens = curl_cmd.split()

    url: str | None = None
    method: str = "POST"
    headers: dict[str, str] = {}
    data_raw: str | None = None

    i = 0
    while i < len(tokens):
        token = tokens[i]

        # Extract URL
        if token.startswith(("http://", "https://")):
            url = token
        elif token in ("--url",) and i + 1 < len(tokens):
            url = tokens[i + 1]
            i += 1
        # Extract Method
        elif token in ("-X", "--request") and i + 1 < len(tokens):
            method = tokens[i + 1].upper()
            i += 1
        # Extract Headers
        elif token in ("-H", "--header") and i + 1 < len(tokens):
            header_val = tokens[i + 1]
            if ":" in header_val:
                k, v = header_val.split(":", 1)
                headers[k.strip()] = v.strip()
            i += 1
        # Extract Cookie flag
        elif token in ("-b", "--cookie") and i + 1 < len(tokens):
            headers["Cookie"] = tokens[i + 1]
            i += 1
        # Extract Body payload
        elif token in ("-d", "--data", "--data-raw") and i + 1 < len(tokens):
            data_raw = tokens[i + 1]
            i += 1

        i += 1

    if not url:
        raise ValueError("Could not detect endpoint URL from cURL command.")

    sample_payload: Any = None
    if data_raw:
        try:
            sample_payload = json.loads(data_raw)
        except json.JSONDecodeError:
            match = re.search(r"(\{.*\}|\[.*\])", data_raw, re.DOTALL)
            if match:
                try:
                    sample_payload = json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass

    return {
        "url": url,
        "method": method,
        "headers": headers,
        "sample_payload": sample_payload,
    }


def detect_array_wrapper(payload: Any) -> tuple[str, list[dict[str, Any]]] | None:
    """Detect if payload root is a dictionary wrapping an array of objects.

    Example: {"courses": [{...}, {...}]} -> ("courses", [{...}, {...}])
    """
    if not isinstance(payload, dict):
        return None

    for key, val in payload.items():
        if isinstance(val, list) and val and all(isinstance(x, dict) for x in val):
            return key, val

    return None


def detect_url_id_candidates(url: str, referer: str = "") -> list[tuple[str, str | None]]:
    """Detect dynamic ID candidates in the URL path, with optional suggested variable name.

    Returns:
        list[tuple[str, str | None]]: [(candidate_id, suggested_param_name), ...]
    """
    path = urlparse(url).path
    segments = [s for s in path.split("/") if s]
    common_words = {
        "api",
        "v1",
        "v2",
        "v3",
        "cms",
        "course",
        "courses",
        "content",
        "learning-plan-content",
        "user",
        "users",
        "items",
        "select",
        "list",
        "detail",
        "update",
        "create",
        "delete",
        "post",
        "get",
        "put",
    }

    candidates: list[tuple[str, str | None]] = []
    for s in segments:
        if s.lower() in common_words:
            continue

        # ID heuristic: digits, UUID, or uppercase alphanumeric with hyphens/numbers
        is_id = (
            s.isdigit()
            or bool(re.match(r"^[0-9a-fA-F-]{36}$", s))
            or (any(c.isupper() for c in s) and (any(c.isdigit() for c in s) or "-" in s))
        )
        if is_id and len(s) >= 4:
            suggested_name: str | None = None
            if referer:
                match = re.search(r"([a-zA-Z0-9_-]+)=" + re.escape(s), referer)
                if match:
                    suggested_name = match.group(1)
            candidates.append((s, suggested_name))

    return candidates
