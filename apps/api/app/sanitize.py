from __future__ import annotations

import re


TAG_RE = re.compile(r"</?([a-zA-Z0-9]+)(?:\s[^>]*)?>")


def sanitize_highlight_html(value: str) -> str:
    """
    Keep only <em> and </em> tags. Strip all other tags.
    """
    if not value:
        return value

    def _replace(match: re.Match[str]) -> str:
        tag = (match.group(1) or "").lower()
        full = match.group(0)
        if tag == "em":
            return "</em>" if full.startswith("</") else "<em>"
        return ""

    return TAG_RE.sub(_replace, value)

