from __future__ import annotations

"""Shared markdown/HTML flattening.

Both the Reducto resume adapter and the job-description fetcher receive markdown
from an upstream API and need it as plain text. They want slightly different
output — the resume parser needs uppercase section headers and live URLs, the JD
fetcher wants neither — so the differences are parameters, not separate copies.
"""

import re
from typing import Callable, Optional

_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK_WITH_URL = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
_LINK_ANY = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_HTML_TAG = re.compile(r"</?[a-zA-Z][^>]*>")
_BULLET = re.compile(r"^\s*[-*+]\s+")
_TABLE_PIPE = re.compile(r"^\s*\|")
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_BLANK_RUN = re.compile(r"\n{3,}")


def _keep_heading(level: int, text: str) -> str:  # noqa: ARG001 - signature is the contract
    return text


def strip_markdown(
    markdown: str,
    *,
    heading: Callable[[int, str], str] = _keep_heading,
    keep_urls: bool = False,
    bullet: str = "- ",
    strip_html: bool = True,
    drop_blank_lines: bool = False,
    max_chars: Optional[int] = None,
) -> str:
    """Flatten markdown to plain text.

    heading:          maps (level, text) -> the line to emit for `#`-style headers
    keep_urls:        `[label](url)` becomes "label url" instead of just "label"
    bullet:           replacement prefix for `-`/`*`/`+` list items
    drop_blank_lines: remove empty lines entirely rather than collapsing runs
    """
    lines = []
    for raw in markdown.split("\n"):
        line = raw.rstrip()

        line = _IMAGE.sub("", line)
        line = _LINK_WITH_URL.sub(r"\1 \2" if keep_urls else r"\1", line)
        line = _LINK_ANY.sub(r"\1", line)
        if strip_html:
            line = _HTML_TAG.sub("", line)
        line = line.replace("**", "").replace("__", "")
        line = _BULLET.sub(bullet, line)
        line = _TABLE_PIPE.sub("", line)

        match = _HEADING.match(line)
        if match:
            line = heading(len(match.group(1)), match.group(2).strip())

        lines.append(line.strip() if drop_blank_lines else line)

    if drop_blank_lines:
        text = "\n".join(l for l in lines if l)
    else:
        text = _BLANK_RUN.sub("\n\n", "\n".join(lines))

    text = text.strip()
    return text[:max_chars] if max_chars else text
