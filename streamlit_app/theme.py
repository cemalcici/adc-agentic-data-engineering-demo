"""The console's look, in one place.

Every value here comes from the table in `ui-context.md`. Nothing else in this
application names a colour, a radius or a font — which is the rule that document
states, and the reason it is worth having.
"""

from __future__ import annotations

TOKENS = {
    "bg-base": "#0B0F14",
    "bg-surface": "#151B23",
    "text-primary": "#E6EDF3",
    "text-muted": "#8B98A5",
    "accent-primary": "#4C9AFF",
    "border-default": "#2A3440",
    "state-success": "#3FB950",
    "state-error": "#F85149",
    "state-pending": "#D29922",
}

FONT_MONO = "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"

# Which token dresses which incident state. Four endings that support opposite
# conclusions about whether any of this works must not read alike — see the
# incident record's own requirement on distinguishable endings.
#
# The two unhappy endings are deliberately different colours. Red is reserved
# for the one where something was written to the transformation project and the
# pipeline still did not recover; the agent giving up cleanly wrote nothing at
# all, and colouring them alike would say they are the same kind of bad news.
STATE_COLOURS = {
    "open": "state-pending",
    "proposed": "state-pending",
    "approved": "accent-primary",
    "resolved": "state-success",
    "rejected": "text-muted",
    "unfixable": "state-pending",
    "verification_failed": "state-error",
}

STATE_LABELS = {
    "open": "diagnosed",
    "proposed": "awaiting your decision",
    "approved": "applying",
    "resolved": "resolved",
    "rejected": "you rejected this",
    "unfixable": "the agent could not fix it",
    "verification_failed": "applied, did not recover",
}

HEALTH_COLOURS = {
    "healthy": "state-success",
    "failing": "state-error",
    "unknown": "state-pending",
    "never run": "text-muted",
}


def css() -> str:
    """Everything Streamlit's own theme cannot express."""
    variables = "\n".join(f"    --{name}: {value};" for name, value in TOKENS.items())
    return f"""
<style>
:root {{
{variables}
    --font-mono: {FONT_MONO};
}}

/* Pill-shaped status badges, always visible at the top of the page. */
.badge {{
    display: inline-block;
    padding: 4px 14px;
    border-radius: 999px;
    font-size: 0.82rem;
    font-weight: 600;
    letter-spacing: 0.02em;
    border: 1px solid var(--border-default);
}}

/* Cards and panels. */
.panel {{
    background: var(--bg-surface);
    border: 1px solid var(--border-default);
    border-radius: 8px;
    padding: 16px 18px;
    margin-bottom: 14px;
}}

.muted {{ color: var(--text-muted); }}
.mono  {{ font-family: var(--font-mono); font-size: 0.86rem; }}

/* The difference. Additions and removals use the same tokens as the status
   colours, so green and red mean one thing across the whole page. */
.diff {{
    font-family: var(--font-mono);
    font-size: 0.82rem;
    line-height: 1.55;
    background: var(--bg-base);
    border: 1px solid var(--border-default);
    border-radius: 8px;
    padding: 12px 14px;
    overflow-x: auto;
    white-space: pre;
}}
.diff .add {{ color: var(--state-success); }}
.diff .del {{ color: var(--state-error); }}
.diff .ctx {{ color: var(--text-muted); }}
.diff .hdr {{ color: var(--accent-primary); }}

/* History rows. */
.row {{
    display: flex;
    gap: 14px;
    align-items: baseline;
    padding: 9px 0;
    border-bottom: 1px solid var(--border-default);
}}
.row .when {{ color: var(--text-muted); font-size: 0.8rem; min-width: 132px; }}

a {{ color: var(--accent-primary); }}
</style>
"""


def badge(text: str, token: str) -> str:
    return (
        f'<span class="badge" style="color: var(--{token}); '
        f'border-color: var(--{token});">{text}</span>'
    )
