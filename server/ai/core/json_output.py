from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

from server.ai.core.errors import AIOutputParseError


_FENCED_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)


def message_content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, Mapping):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def extract_json_object(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        raise AIOutputParseError("model output does not contain a JSON object")

    for match in _FENCED_BLOCK_RE.finditer(stripped):
        try:
            return extract_json_object(match.group(1))
        except AIOutputParseError:
            continue

    start = stripped.find("{")
    if start < 0:
        raise AIOutputParseError("model output does not contain a JSON object")

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(stripped)):
        char = stripped[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return stripped[start : index + 1]

    raise AIOutputParseError("model output does not contain a complete JSON object")


def parse_json_object(text: str) -> dict[str, Any]:
    json_text = extract_json_object(text)
    try:
        value = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise AIOutputParseError(f"model output contains invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise AIOutputParseError("model output JSON root must be an object")
    return value
