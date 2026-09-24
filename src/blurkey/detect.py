"""Secret detectors: regexes over OCR line text.

Order matters: specific detectors run before generic ones.
Overlapping matches are merged (first / most-specific wins).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

VALID_KINDS = (
    "aws",
    "github",
    "openai",
    "anthropic",
    "stripe",
    "slack",
    "google",
    "jwt",
    "bearer",
    "assignment",
    "private_key",
    "email",
    "ipv4",
    "high_entropy",
)


@dataclass
class RawMatch:
    kind: str
    value: str
    start: int
    end: int


# --- specific patterns (ordered) ---
_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("aws", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("github", re.compile(r"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{20,})")),
    ("anthropic", re.compile(r"sk-ant-[A-Za-z0-9\-_]{20,}")),
    ("openai", re.compile(r"sk-[A-Za-z0-9\-_]{20,}")),
    ("stripe", re.compile(r"(?:sk|pk|rk)_(?:live|test)_[A-Za-z0-9]{16,}")),
    ("slack", re.compile(r"xox[bpras]-[A-Za-z0-9\-]{10,}")),
    ("google", re.compile(r"AIza[0-9A-Za-z\-_]{20,}")),
    ("jwt", re.compile(r"eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+")),
    ("bearer", re.compile(r"Bearer\s+([A-Za-z0-9\-._~+/=]{20,})", re.IGNORECASE)),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    # assignment: redact the VALUE only, e.g. api_key=SECRET / password: SECRET
    # \w* prefix/suffix allows AWS_ACCESS_KEY_ID, CLIENT_SECRET, AUTH_TOKEN, etc.
    ("assignment", re.compile(
        r"(?i)\w*(?:api[_-]?key|access[_-]?key|secret|passwd|password|pwd|token)\w*\s*[:=]\s*['\"]?([^\s'\";,]+)['\"]?"
    )),
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("ipv4", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
]

# Lenient OCR-garble patterns (same kind, run after strict; over-cover is safe).
# AWS: OCR often inserts a space -> "AKIAIOSFODNN7 EXAMPLE"
_LENIENT_AWS_RE = re.compile(r"AKIA(?:\s?[0-9A-Z]){16}")
_STRICT_AWS_RE = re.compile(r"AKIA[0-9A-Z]{16}")
# Email: OCR often inserts spaces -> "alice @example.com", "a@b .com"
_LENIENT_EMAIL_RE = re.compile(
    r"[A-Za-z0-9._%+-]+\s*@\s*[A-Za-z0-9.-]+\s*\.\s*[A-Za-z]{2,}"
)
_STRICT_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_HEX_RE = re.compile(r"^[0-9a-fA-F]+$")
_SHA_RE = re.compile(r"^[0-9a-f]{7,40}$|^[0-9A-F]{7,40}$")
_TOKEN_RE = re.compile(r"[A-Za-z0-9_\-+/=]{24,}")


def _shannon(s: str) -> float:
    if not s:
        return 0.0
    from collections import Counter
    counts = Counter(s)
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def _valid_ipv4(tok: str) -> bool:
    try:
        parts = tok.split(".")
        return len(parts) == 4 and all(0 <= int(p) <= 255 for p in parts)
    except ValueError:
        return False


def _is_excluded_token(tok: str) -> bool:
    """Exclude git SHAs and UUIDs from high-entropy detection."""
    if _UUID_RE.match(tok):
        return True
    # plain hex of sha-like length is likely a commit hash
    if _HEX_RE.match(tok) and 7 <= len(tok) <= 64:
        return True
    if _SHA_RE.match(tok):
        return True
    return False


def detect_line(
    text: str,
    *,
    only: set[str] | None = None,
    skip: set[str] | None = None,
    allow: re.Pattern | None = None,
) -> list[RawMatch]:
    """Detect secrets in a single OCR line. Returns non-overlapping matches."""
    only = only or set()
    skip = skip or set()
    candidates: list[RawMatch] = []

    for kind, rx in _PATTERNS:
        if only and kind not in only:
            continue
        if kind in skip:
            continue
        for m in rx.finditer(text):
            if kind in ("assignment", "bearer"):
                # group 1 is the value; redact value only, keep label visible
                try:
                    val = m.group(1)
                    s, e = m.start(1), m.end(1)
                except IndexError:
                    val = m.group(0)
                    s, e = m.start(), m.end()
                if len(val) < 4:
                    continue
            else:
                val = m.group(0)
                s, e = m.start(), m.end()
                if kind == "ipv4" and not _valid_ipv4(val):
                    continue
            if allow is not None and allow.search(val):
                continue
            candidates.append(RawMatch(kind, val, s, e))

    def _lenient_allowed(kind: str) -> bool:
        if kind in skip:
            return False
        if only and kind not in only:
            return False
        return True

    # Lenient AWS: tolerate OCR-inserted spaces ("AKIAIOSFODNN7 EXAMPLE").
    # Span covers the spaced form (over-cover safe); value is de-spaced.
    if _lenient_allowed("aws"):
        for m in _LENIENT_AWS_RE.finditer(text):
            raw = m.group(0)
            stripped = raw.replace(" ", "")
            if not _STRICT_AWS_RE.fullmatch(stripped):
                continue
            s, e = m.start(), m.end()
            if allow is not None and (
                allow.search(raw) or allow.search(stripped)
            ):
                continue
            candidates.append(RawMatch("aws", stripped, s, e))

    # Lenient email: tolerate spaces around @ and . ("alice @example.com").
    if _lenient_allowed("email"):
        for m in _LENIENT_EMAIL_RE.finditer(text):
            raw = m.group(0)
            stripped = raw.replace(" ", "")
            if not _STRICT_EMAIL_RE.fullmatch(stripped):
                continue
            s, e = m.start(), m.end()
            if allow is not None and (
                allow.search(raw) or allow.search(stripped)
            ):
                continue
            candidates.append(RawMatch("email", stripped, s, e))

    # generic high-entropy pass (last)
    # collect spans of skipped specifics so generic doesn't re-claim them
    skipped_spans: list[tuple[int, int]] = []
    if skip:
        for kind, rx in _PATTERNS:
            if kind not in skip:
                continue
            # respect --only: if only is set and kind not in only, it wouldn't
            # have fired anyway, so no need to suppress generic for it
            if only and kind not in only:
                continue
            for m in rx.finditer(text):
                if kind in ("assignment", "bearer"):
                    try:
                        s, e = m.start(1), m.end(1)
                    except IndexError:
                        s, e = m.start(), m.end()
                else:
                    s, e = m.start(), m.end()
                skipped_spans.append((s, e))
        # lenient spans also suppress generic when their kind is skipped
        if "aws" in skip and (not only or "aws" in only):
            for m in _LENIENT_AWS_RE.finditer(text):
                if _STRICT_AWS_RE.fullmatch(m.group(0).replace(" ", "")):
                    skipped_spans.append((m.start(), m.end()))
        if "email" in skip and (not only or "email" in only):
            for m in _LENIENT_EMAIL_RE.finditer(text):
                if _STRICT_EMAIL_RE.fullmatch(m.group(0).replace(" ", "")):
                    skipped_spans.append((m.start(), m.end()))
    if (not only or "high_entropy" in only) and "high_entropy" not in skip:
        for m in _TOKEN_RE.finditer(text):
            tok = m.group(0)
            s, e = m.start(), m.end()
            if any(s < oe and os < e for os, oe in skipped_spans):
                continue
            if _is_excluded_token(tok):
                continue
            if _shannon(tok) < 4.0:
                continue
            if allow is not None and allow.search(tok):
                continue
            candidates.append(RawMatch("high_entropy", tok, s, e))

    # merge overlaps: specific detectors win over generic high-entropy.
    # candidates were added specific-first, so keep that priority.
    # split: everything before generic pass vs generic pass
    first_generic = next(
        (i for i, c in enumerate(candidates) if c.kind == "high_entropy"),
        len(candidates),
    )
    specific = sorted(candidates[:first_generic], key=lambda r: (r.start, -(r.end - r.start)))
    generic = sorted(candidates[first_generic:], key=lambda r: (r.start, -(r.end - r.start)))
    ordered = specific + generic
    merged: list[RawMatch] = []
    occupied: list[tuple[int, int]] = []
    for c in ordered:
        overlap = any(c.start < oe and oe_start < c.end for oe_start, oe in occupied)
        if overlap:
            continue
        merged.append(c)
        occupied.append((c.start, c.end))
    merged.sort(key=lambda r: r.start)
    return merged
