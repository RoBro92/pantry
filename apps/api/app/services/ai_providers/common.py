from __future__ import annotations

import json
from typing import Any


def parse_json_output(output_text: str) -> dict[str, object]:
    cleaned = output_text.strip()
    if not cleaned:
        raise ValueError("Provider returned an empty response.")

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if len(lines) >= 3 and lines[-1].strip() == "```":
                fenced = "\n".join(lines[1:-1]).strip()
                return json.loads(fenced)
        raise


def sanitize_openai_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    return _sanitize_openai_schema_node(schema)


def _sanitize_openai_schema_node(node: Any) -> Any:
    if isinstance(node, list):
        return [_sanitize_openai_schema_node(item) for item in node]
    if not isinstance(node, dict):
        return node

    sanitized: dict[str, Any] = {}
    for key, value in node.items():
        if key in {"default", "title", "examples"}:
            continue
        if key == "properties" and isinstance(value, dict):
            sanitized[key] = {
                property_name: _sanitize_openai_schema_node(property_schema)
                for property_name, property_schema in value.items()
            }
            continue
        if key == "$defs" and isinstance(value, dict):
            sanitized[key] = {
                definition_name: _sanitize_openai_schema_node(definition_schema)
                for definition_name, definition_schema in value.items()
            }
            continue
        sanitized[key] = _sanitize_openai_schema_node(value)

    properties = sanitized.get("properties")
    if isinstance(properties, dict):
        sanitized["additionalProperties"] = False
        sanitized["required"] = list(properties.keys())

    return sanitized
