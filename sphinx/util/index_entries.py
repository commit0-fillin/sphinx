from __future__ import annotations

def _split_into(n: int, type: str, value: str) -> list[str]:
    """Split an index entry into a given number of parts at semicolons."""
    parts = value.split(';', n - 1)
    if len(parts) < n:
        parts.extend([''] * (n - len(parts)))
    return parts[:n]
