from __future__ import annotations

import json


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
