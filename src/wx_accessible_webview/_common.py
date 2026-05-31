"""Shared building blocks for the accessible WebView surfaces.

Everything here is platform-agnostic string/HTML work — no wx import — so it's
cheap to share across the embeddable view, the modal dialog, the live preview
pane, and the chat surface.
"""

from __future__ import annotations

import html
import json
import re

#: Readable, high-contrast, forced-colors-aware styles used by every surface.
DEFAULT_STYLES = """
  :root { color-scheme: light dark; }
  html, body { margin: 0; padding: 0; }
  body { font-family: system-ui, Segoe UI, Arial, sans-serif; font-size: 1.05rem;
         line-height: 1.6; padding: 12px 16px; }
  h1, h2, h3, h4, h5, h6 { scroll-margin-top: 1.5rem; }
  article { margin: 0 0 14px 0; padding: 10px 12px; border-radius: 8px;
            border: 1px solid GrayText; }
  pre { background: Field; padding: 10px; border-radius: 8px; overflow-x: auto;
        white-space: pre-wrap; word-break: break-word; }
  code { font-family: ui-monospace, Consolas, monospace; }
  blockquote { border-left: 4px solid GrayText; padding-left: 1rem; }
  table { border-collapse: collapse; }
  th, td { border: 1px solid GrayText; padding: 0.4rem 0.6rem; }
  a { color: LinkText; }
  :focus { outline: 2px solid Highlight; outline-offset: 2px; }
  .visually-hidden { position: absolute; width: 1px; height: 1px; overflow: hidden;
                     clip: rect(0 0 0 0); white-space: nowrap; }
  @media (forced-colors: active) {
    article, th, td { border: 1px solid CanvasText; }
    blockquote { border-left-color: CanvasText; }
  }
"""


def strip_tags(markup: str) -> str:
    """Best-effort HTML->text, used for the no-WebView text fallback."""
    return html.unescape(re.sub(r"<[^>]+>", "", markup or ""))


def key_bridge_js(handler_name: str, keys_to_type: dict[str, str]) -> str:
    """Build a keydown listener that posts ``{type: <value>}`` to Python.

    The native WebView swallows keys like Escape and F6, so we listen in the
    page and bridge them out through the script-message handler.

    ``keys_to_type`` maps a JS ``event.key`` value (e.g. ``"Escape"``) to the
    message ``type`` string Python should receive (e.g. ``"__close"``).
    """
    if not keys_to_type:
        return ""
    cases = " || ".join(f"e.key==={json.dumps(k)}" for k in keys_to_type)
    # Map each key to its message type at send time.
    mapping = json.dumps(keys_to_type)
    return (
        "document.addEventListener('keydown',function(e){"
        f"var m={mapping};"
        f"if({cases}){{e.preventDefault();var t=m[e.key];"
        f"if(window.{handler_name}&&window.{handler_name}.postMessage)"
        f"{{window.{handler_name}.postMessage(JSON.stringify({{type:t}}));}}}}"
        "});"
    )


def document(
    *,
    title: str,
    lang: str,
    styles: str,
    body: str,
    scripts: str = "",
) -> str:
    """Wrap a body fragment in a complete, semantic HTML document."""
    t = html.escape(title)
    script_block = f"<script>{scripts}</script>" if scripts else ""
    return (
        "<!DOCTYPE html>\n"
        f'<html lang="{html.escape(lang)}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{t}</title><style>{styles}</style></head>"
        f"<body>{body}{script_block}</body></html>"
    )
