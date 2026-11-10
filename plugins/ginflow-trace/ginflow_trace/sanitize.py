"""Safe, bounded conversion of trace payloads."""

from __future__ import annotations

from collections.abc import Mapping

SENSITIVE = {"token", "password", "secret", "cookie", "authorization", "api_key", "apikey", "credential"}
MAX_TEXT = 4096
MAX_ITEMS = 100


def sanitize(value: object, depth: int = 0) -> object:
    if depth > 5:
        return "<truncated>"
    if isinstance(value, Mapping):
        result = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= MAX_ITEMS:
                result["<truncated>"] = "<truncated>"
                break
            name = str(key)
            result[name] = "<redacted>" if any(part in name.lower() for part in SENSITIVE) else sanitize(item, depth + 1)
        return result
    if isinstance(value, (list, tuple, set)):
        items = [sanitize(item, depth + 1) for item in list(value)[:MAX_ITEMS]]
        if len(value) > MAX_ITEMS:
            items.append("<truncated>")
        return items
    if isinstance(value, str):
        return value[:MAX_TEXT] + "<truncated>" if len(value) > MAX_TEXT else value
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return sanitize(repr(value), depth + 1)
