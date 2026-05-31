"""Embeddable accessible ``wx.html2.WebView`` surfaces.

``wx.html2.WebView`` is a factory-created native control (Edge **WebView2** on
Windows, WKWebView on macOS, WebKitGTK on Linux). Because it's native and
factory-built it can't be meaningfully subclassed to "make it accessible" — and
embedded in a wxPython app it has historically read inconsistently in NVDA and
often not at all in **JAWS**.

The trick: a WebView's accessibility is driven by the **HTML you render into
it**, not by the wx widget. So instead of fighting the control, these surfaces
render a semantic, screen-reader-friendly document — and the screen reader
follows it like any web page (verified in **NVDA *and* JAWS**).

This module provides the two *embeddable* surfaces:

* :class:`AccessibleWebView` — a general content view with an optional ARIA live
  region, a status region, a JS->Python bridge, optional Escape/F6 key bridges,
  optional "open links in the system browser", focus management, and a text
  fallback when no WebView backend exists.
* :class:`SidePreview` — a live preview pane (e.g. beside an editor) whose
  :meth:`SidePreview.update` swaps the body in place so scroll position and
  screen-reader position survive each re-render.

Modal dialogs live in :mod:`wx_accessible_webview.dialog`; the chat surface with
an in-page composer lives in :mod:`wx_accessible_webview.chat`.

This is a generalized extraction of the wrapper built for Quill (the
screen-reader-first editor, a Community Access project).
"""

from __future__ import annotations

import json

from wx_accessible_webview._common import (
    DEFAULT_STYLES,
    document,
    key_bridge_js,
    strip_tags,
)


class AccessibleWebView:
    """An accessible, embeddable ``wx.html2.WebView`` wrapper.

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
        Name of the JS bridge object (``window.<handler_name>.postMessage(...)``).
    on_message:
        Callback ``on_message(data: dict)`` for messages posted from the page.
    on_close:
        Callback invoked when the page asks to close (requires ``escape_to_close``).
    on_return:
        Callback invoked when the user presses Escape **or F6** to hand focus
        back (e.g. from a side preview to the editor). When set, this takes the
        place of ``escape_to_close``'s Escape handling.
    escape_to_close:
        If True, pressing Escape inside the WebView calls ``on_close`` (the key
        is bridged out of the native control, which otherwise swallows it).
    open_links_externally:
        If True, clicking an ``http(s)`` link opens it in the system browser
        instead of navigating the embedded view. Guarded so it never interferes
        with the initial render.
    initial_html:
        Optional HTML baked into the first page (avoids an empty->rendered flash).
    styles:
        CSS for the document ``<style>`` block.
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
        on_return=None,
        escape_to_close: bool = False,
        open_links_externally: bool = False,
        initial_html: str = "",
        styles: str = DEFAULT_STYLES,
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
        self._on_return = on_return
        self._escape_to_close = escape_to_close
        self._open_links_externally = open_links_externally
        self._styles = styles

        try:
            import wx.html2 as webview

            self.view = webview.WebView.New(parent)
            self.view.SetName(title)
            try:
                self.view.AddScriptMessageHandler(handler_name)
                self.view.Bind(webview.EVT_WEBVIEW_SCRIPT_MESSAGE_RECEIVED, self._on_script_message)
            except Exception:  # noqa: BLE001
                pass  # older backend: no bridge, but content still renders
            self.view.Bind(webview.EVT_WEBVIEW_LOADED, self._on_loaded)
            if open_links_externally:
                self.view.Bind(webview.EVT_WEBVIEW_NAVIGATING, self._on_navigating)
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

    def clear(self) -> None:
        """Reset to an empty document (re-renders the skeleton)."""
        if self.fallback is not None:
            self.fallback.SetValue("")
            return
        self._ready = False
        self._pending = []
        self.view.SetPage(self._skeleton(""), "")

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

    def _on_navigating(self, event: object) -> None:
        url = event.GetURL() or ""
        # Only divert real link clicks after load; never the initial page load.
        if self._ready and url.startswith(("http://", "https://")):
            event.Veto()
            import webbrowser

            webbrowser.open(url)

    def _on_script_message(self, event: object) -> None:
        try:
            data = json.loads(event.GetString())
        except Exception:  # noqa: BLE001
            return
        kind = data.get("type")
        if kind == "__close":
            if self._on_close is not None:
                self._on_close()
            return
        if kind == "__return":
            if self._on_return is not None:
                self._on_return()
            return
        if self._on_message is not None:
            self._on_message(data)

    def _run(self, script: str) -> None:
        try:
            self.view.RunScript(script)
        except Exception:  # noqa: BLE001
            pass

    def _bridge_keys(self) -> dict[str, str]:
        keys: dict[str, str] = {}
        if self._on_return is not None:
            keys["Escape"] = "__return"
            keys["F6"] = "__return"
        elif self._escape_to_close:
            keys["Escape"] = "__close"
        return keys

    def _skeleton(self, initial_html: str) -> str:
        import html as _html

        role = 'role="log" aria-live="polite"' if self._live_region else 'role="region"'
        title = _html.escape(self._title)
        body = (
            '<div id="awv-status" role="status" aria-live="assertive" '
            'class="visually-hidden"></div>'
            f'<main id="content" {role} aria-label="{title}" tabindex="0">'
            f"\n{initial_html}\n</main>"
        )
        scripts = (
            "(function(){"
            "var content=document.getElementById('content');"
            "var statusEl=document.getElementById('awv-status');"
            "window.__awv={"
            "append:function(h){var t=document.createElement('div');t.innerHTML=h;"
            "while(t.firstChild){content.appendChild(t.firstChild);}"
            "content.scrollTop=content.scrollHeight;},"
            "set:function(h){content.innerHTML=h;},"
            "status:function(s){if(statusEl){statusEl.textContent=s;}},"
            "focus:function(){content.focus();}"
            "};"
            f"{key_bridge_js(self._handler_name, self._bridge_keys())}"
            "})();"
        )
        return document(
            title=self._title,
            lang=self._lang,
            styles=self._styles,
            body=body,
            scripts=scripts,
        )


class SidePreview:
    """A live preview pane — e.g. shown to the right of an editor in a splitter.

    :meth:`update` replaces the rendered body in place (via ``innerHTML``) so
    scroll position is preserved while the user types, rather than reloading the
    whole page each keystroke. Pressing Escape or F6 inside the pane fires
    ``on_return`` (hand focus back to the editor). Falls back to a read-only text
    control where no WebView backend exists.

    You render Markdown/HTML yourself and pass the resulting HTML to
    :meth:`update`; this stays dependency-light (wxPython only).
    """

    def __init__(
        self,
        parent,
        *,
        title: str = "Preview",
        lang: str = "en",
        on_return=None,
        handler_name: str = "awv",
        open_links_externally: bool = True,
        styles: str = DEFAULT_STYLES,
    ) -> None:
        # A SidePreview is an AccessibleWebView with no live region (it's a
        # rendered document, not a log) and a return bridge for Escape/F6.
        self._view = AccessibleWebView(
            parent,
            title=title,
            lang=lang,
            live_region=False,
            handler_name=handler_name,
            on_return=on_return,
            open_links_externally=open_links_externally,
            styles=styles,
        )

    @property
    def control(self):
        return self._view.control

    @property
    def using_webview(self) -> bool:
        return self._view.using_webview

    def update(self, body_html: str) -> None:
        """Replace the preview body in place."""
        self._view.set_content(body_html)

    def focus(self) -> None:
        self._view.focus()
