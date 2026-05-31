"""An accessible wrapper around ``wx.html2.WebView``.

``wx.html2.WebView`` is a factory-created native control (Edge **WebView2** on
Windows, WKWebView on macOS, WebKitGTK on Linux). Because it's native and
factory-built it can't be meaningfully subclassed to "make it accessible" — and
embedded in a wxPython app it has historically read inconsistently in NVDA and
often not at all in **JAWS**.

The trick this wrapper uses: a WebView's accessibility is driven by the **HTML
you render into it**, not by the wx widget. So instead of fighting the control,
it renders a semantic, screen-reader-friendly document — and the screen reader
follows it like any web page (verified in **NVDA *and* JAWS**).

What you get:
  * a semantic page: ``lang``, viewport, readable + high-contrast/forced-colors CSS;
  * an optional **ARIA live region** (``role="log" aria-live="polite"``) so
    appended content is announced automatically;
  * an assertive ``role="status"`` region for transient announcements;
  * a **JS->Python bridge** (``window.<name>.post(obj)``) so the page can send
    events back to Python;
  * optional **Escape-to-close** bridged out of the native control (which
    swallows the key);
  * focus management into the content;
  * a graceful **read-only text fallback** when no WebView backend is available.

This is a generalized extraction of the wrapper built for Quill (the
screen-reader-first editor by BITS / Community Access).
"""
from __future__ import annotations

import html
import json

_DEFAULT_STYLES = """
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


class AccessibleWebView:
    """An accessible ``wx.html2.WebView`` wrapper.

    Parameters
    ----------
    parent:
        The parent wx window.
    title:
        Accessible name for the control and the document ``<title>``.
    lang:
        Document language (``<html lang>``).
    live_region:
        If True (default) the content area is an ARIA live region, so calls to
        :meth:`append` are announced automatically.
    handler_name:
        Name of the JS bridge object (``window.<handler_name>.post(obj)``).
    on_message:
        Callback ``on_message(data: dict)`` for messages posted from the page.
    on_close:
        Callback invoked when the page asks to close (see ``escape_to_close``).
    escape_to_close:
        If True, pressing Escape inside the WebView calls ``on_close`` (the key
        is bridged out of the native control, which otherwise swallows it).
    initial_html:
        Optional HTML to bake into the first page (avoids an empty->rendered flash).
    """

    def __init__(
        self,
        parent,
        *,
        title: str = "Content",
        lang: str = "en",
        live_region: bool = True,
        handler_name: str = "awv",
        on_message=None,
        on_close=None,
        escape_to_close: bool = False,
        initial_html: str = "",
        styles: str = _DEFAULT_STYLES,
    ) -> None:
        import wx

        self._wx = wx
        self.view = None
        self.fallback = None
        self._ready = False
        self._pending: list[tuple[str, object]] = []
        self._want_focus = False
        self._title = title
        self._lang = lang
        self._live_region = live_region
        self._handler_name = handler_name
        self._on_message = on_message
        self._on_close = on_close
        self._escape_to_close = escape_to_close
        self._styles = styles

        try:
            import wx.html2 as webview

            self.view = webview.WebView.New(parent)
            self.view.SetName(title)
            try:
                self.view.AddScriptMessageHandler(handler_name)
                self.view.Bind(
                    webview.EVT_WEBVIEW_SCRIPT_MESSAGE_RECEIVED, self._on_script_message
                )
            except Exception:  # noqa: BLE001
                pass  # older backend: no bridge, but content still renders
            self.view.Bind(webview.EVT_WEBVIEW_LOADED, self._on_loaded)
            self.view.SetPage(self._skeleton(initial_html), "")
        except Exception:  # noqa: BLE001
            # No WebView backend: degrade to a read-only text control.
            self.view = None
            self.fallback = wx.TextCtrl(
                parent, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2
            )
            self.fallback.SetName(title)
            if initial_html:
                self.fallback.SetValue(strip_tags(initial_html))

    # -- public API --------------------------------------------------------

    @property
    def control(self):
        """The underlying wx control (WebView, or the text fallback)."""
        return self.view if self.view is not None else self.fallback

    @property
    def using_webview(self) -> bool:
        return self.view is not None

    def append(self, html_fragment: str) -> None:
        """Append an HTML fragment to the content area (announced if live_region)."""
        if self.fallback is not None:
            self.fallback.AppendText(strip_tags(html_fragment) + "\n")
            return
        self._do("append", html_fragment)

    def set_content(self, html_body: str) -> None:
        """Replace the whole content area with an HTML fragment."""
        if self.fallback is not None:
            self.fallback.SetValue(strip_tags(html_body))
            return
        self._do("set", html_body)

    def status(self, text: str) -> None:
        """Announce transient status via the assertive status region."""
        if self.fallback is not None:
            return
        self._do("status", text)

    def focus(self) -> None:
        """Move focus into the content area."""
        if self.fallback is not None:
            self.fallback.SetFocus()
            return
        self.view.SetFocus()
        if self._ready:
            self._run("window.__awv.focus();")
        else:
            self._want_focus = True

    def run_js(self, script: str) -> None:
        if self.view is not None:
            self._run(script)

    # -- internals ---------------------------------------------------------

    def _do(self, kind: str, payload: object) -> None:
        if self._ready:
            self._dispatch(kind, payload)
        else:
            self._pending.append((kind, payload))

    def _dispatch(self, kind: str, payload: object) -> None:
        if kind == "append":
            self._run(f"window.__awv.append({json.dumps(payload)});")
        elif kind == "set":
            self._run(f"window.__awv.set({json.dumps(payload)});")
        elif kind == "status":
            self._run(f"window.__awv.status({json.dumps(payload)});")

    def _on_loaded(self, _event: object) -> None:
        self._ready = True
        pending, self._pending = self._pending, []
        for kind, payload in pending:
            self._dispatch(kind, payload)
        if self._want_focus:
            self._want_focus = False
            self.view.SetFocus()
            self._run("window.__awv.focus();")

    def _on_script_message(self, event: object) -> None:
        try:
            data = json.loads(event.GetString())
        except Exception:  # noqa: BLE001
            return
        if data.get("type") == "__close":
            if self._on_close is not None:
                self._on_close()
            return
        if self._on_message is not None:
            self._on_message(data)

    def _run(self, script: str) -> None:
        try:
            self.view.RunScript(script)
        except Exception:  # noqa: BLE001
            pass

    def _skeleton(self, initial_html: str) -> str:
        title = html.escape(self._title)
        role = 'role="log" aria-live="polite"' if self._live_region else 'role="region"'
        escape_js = ""
        if self._escape_to_close:
            escape_js = (
                "document.addEventListener('keydown',function(e){"
                "if(e.key==='Escape'){e.preventDefault();"
                f"if(window.{self._handler_name}&&window.{self._handler_name}.postMessage)"
                f"{{window.{self._handler_name}.postMessage(JSON.stringify({{type:'__close'}}));}}"
                "}});"
            )
        return f"""<!DOCTYPE html>
<html lang="{html.escape(self._lang)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{self._styles}</style>
</head>
<body>
<div id="awv-status" role="status" aria-live="assertive" class="visually-hidden"></div>
<main id="content" {role} aria-label="{title}" tabindex="0">
{initial_html}
</main>
<script>
  (function() {{
    var content = document.getElementById('content');
    var statusEl = document.getElementById('awv-status');
    window.__awv = {{
      append: function(htmlFragment) {{
        var tmp = document.createElement('div');
        tmp.innerHTML = htmlFragment;
        while (tmp.firstChild) {{ content.appendChild(tmp.firstChild); }}
        content.scrollTop = content.scrollHeight;
      }},
      set: function(htmlBody) {{ content.innerHTML = htmlBody; }},
      status: function(text) {{ if (statusEl) {{ statusEl.textContent = text; }} }},
      focus: function() {{ content.focus(); }}
    }};
    {escape_js}
  }})();
</script>
</body>
</html>"""


def strip_tags(markup: str) -> str:
    """Best-effort HTML->text for the no-WebView fallback."""
    import re

    return html.unescape(re.sub(r"<[^>]+>", "", markup or ""))
