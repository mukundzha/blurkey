"""Human + machine-readable reports. Never prints full secret values."""
from __future__ import annotations


def summarize(kinds: dict[str, int], *, check_mode: bool = False) -> str:
    total = sum(kinds.values())
    if total == 0:
        return "No secrets found"
    parts = [f"{v} {k}" for k, v in sorted(kinds.items())]
    noun = "item" if total == 1 else "items"
    verb = "Found" if check_mode else "Redacted"
    return f"{verb} {total} {noun}: " + ", ".join(parts)


def safe_prefix(value: str, n: int = 4) -> str:
    return value[:n]


def report_dict(
    path: str,
    kinds: dict[str, int],
    out: str | None,
    extra: dict | None = None,
) -> dict:
    d: dict = {
        "file": path,
        "output": out,
        "total": sum(kinds.values()),
        "kinds": kinds,
    }
    if extra:
        d.update(extra)
    return d
