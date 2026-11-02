"""Check a JSON value against a C# type as Unity's Newtonsoft.Json would read it.

Non-nullable value types (int, bool) must be present and non-null, or Unity
throws during deserialization. Reference types (string, arrays, nested DTOs)
may be null.
"""
from __future__ import annotations

from typing import Any


def matches_csharp_type(value: Any, csharp_type: str) -> bool:
    if csharp_type == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if csharp_type == "int?":
        return value is None or (isinstance(value, int) and not isinstance(value, bool))
    if csharp_type == "bool":
        return isinstance(value, bool)
    if csharp_type == "string":
        return value is None or isinstance(value, str)
    if csharp_type == "string[]":
        return value is None or (isinstance(value, list) and all(isinstance(v, str) for v in value))
    if csharp_type == "int[]":
        return value is None or (
            isinstance(value, list) and all(isinstance(v, int) and not isinstance(v, bool) for v in value)
        )
    if csharp_type.endswith("Dto") or csharp_type == "object":
        return value is None or isinstance(value, dict)
    if csharp_type == "SupportType":
        return isinstance(value, str)
    raise AssertionError(f"unhandled C# type {csharp_type!r}")


def non_nullable(csharp_type: str) -> bool:
    return csharp_type in {"int", "bool"}
