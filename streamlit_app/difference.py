"""Turning two versions of a file into something a reviewer can read.

Derived on every render rather than stored. The incident carries whole contents
before and after precisely so this is possible — a difference is a good way to
show a change and a poor way to carry one.

See adr/0017-carry-proposed-fixes-as-file-contents.md
"""

from __future__ import annotations

import difflib
import html

CLASSES = {"+": "add", "-": "del", "@": "hdr"}


def unified(before: str, after: str, path: str) -> str:
    """A unified difference, marked up for the console's stylesheet.

    Three lines of context. Enough to see where a change sits in the file
    without reprinting a file the operator can already read above it.
    """
    lines = difflib.unified_diff(
        before.splitlines(),
        after.splitlines(),
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
        lineterm="",
        n=3,
    )
    rendered = []
    for line in lines:
        # `---` and `+++` are the file headers, not additions and removals; they
        # would otherwise be coloured as though the whole file changed.
        marker = "@" if line.startswith(("---", "+++")) else line[:1]
        rendered.append(
            f'<span class="{CLASSES.get(marker, "ctx")}">{html.escape(line)}</span>'
        )
    if not rendered:
        return '<div class="diff"><span class="ctx">no change</span></div>'
    return '<div class="diff">' + "\n".join(rendered) + "</div>"


def counts(before: str, after: str) -> tuple[int, int]:
    """How many lines were added and removed, for a one-line summary."""
    added = removed = 0
    for line in difflib.unified_diff(
        before.splitlines(), after.splitlines(), lineterm="", n=0
    ):
        if line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1
    return added, removed
