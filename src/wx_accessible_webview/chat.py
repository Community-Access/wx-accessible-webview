"""An accessible chat surface built on ``wx.html2.WebView``.

The *whole* conversation — transcript, suggestion chips, and the message edit
field — renders as one semantic, screen-reader-friendly document:

* an ARIA live region (``role="log" aria-live="polite"``) so new messages are
  announced automatically;
* an assertive ``role="status"`` region for transient state ("Thinking…");
* each turn is an ``<article>`` with a speaker ``<h2>`` for heading navigation;
* a labelled in-page ``<textarea>``: Enter sends, Shift+Enter inserts a newline;
* suggestion chips that hide after the first message (like Apple Intelligence);
* Escape bridged out of the native control to close.

You render each message's Markdown to HTML yourself (any renderer) and pass the
HTML to :meth:`AccessibleChatView.append_message`, keeping this dependency-light.

This generalizes Quill's Ask Quill chat surface.
"""

from __future__ import annotations

import html
import json

from wx_accessible_webview._common import document

_CHAT_STYLES = """
  :root { color-scheme: light dark; }
  html, body { margin: 0; padding: 0; height: 100%; }
  body { font-family: system-ui, Segoe UI, Arial, sans-serif; font-size: 1.05rem;
         line-height: 1.5; display: flex; flex-direction: column; height: 100vh; }
  main#log { display: block; flex: 1 1 auto; overflow-y: auto; padding: 12px; }
  article { margin: 0 0 14px 0; padding: 10px 12px; border-radius: 8px;
            border: 1px solid GrayText; }
  article.you { background: Field; }
  article h2 { font-size: 0.95rem; margin: 0 0 6px 0; }
  article p { margin: 0.4em 0; }
  pre { background: Field; padding: 8px; overflow-x: auto; white-space: pre-wrap; }
  code { font-family: ui-monospace, Consolas, monospace; }
  a { color: LinkText; }
  :focus { outline: 2px solid Highlight; outline-offset: 2px; }
  #suggestions { display: flex; flex-wrap: wrap; gap: 6px; padding: 0 12px 8px; }
  #suggestions[hidden] { display: none; }
  button.suggestion { font-size: 0.95rem; padding: 4px 10px; border-radius: 14px;
                      border: 1px solid GrayText; background: ButtonFace;
                      color: ButtonText; cursor: pointer; }
  form#composer { display: flex; gap: 8px; align-items: flex-end;
                  padding: 8px 12px 12px; border-top: 1px solid GrayText; }
  form#composer label { position: absolute; width: 1px; height: 1px;
                        overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
  #msg { flex: 1 1 auto; font: inherit; padding: 8px; resize: vertical;
         min-height: 2.4em; }
  #send { font: inherit; padding: 8px 16px; }
  .visually-hidden { position: absolute; width: 1px; height: 1px; overflow: hidden;
                     clip: rect(0 0 0 0); white-space: nowrap; }
  @media (forced-colors: active) { article { border: 1px solid CanvasText; } }
"""


class AccessibleChatView:
    """An accessible chat surface with an in-page composer and suggestion chips.

    Parameters
    ----------
    parent:
        The parent wx window.
    title:
        Accessible name for the transcript region and document title.
    intro:
        Optional ``(speaker, html_body)`` baked into the first page so there's no
        empty->rendered flash. ``html_body`` is already-rendered HTML.
    suggestions:
        Suggestion chip labels; clicking one sends it. They hide after the first
        message (or call :meth:`hide_suggestions`).
    placeholder:
        Placeholder text for the message field.
    composer_label:
        Accessible label for the message field.
    send_label:
        Label for the send button.
    on_send:
        Callback ``on_send(text: str)`` when the user submits a message.
    on_close:
        Callback when the user presses Escape.
    lang:
        Document language.
    """

    def __init__(
        self,
        parent,
        *,
        title: str = "Conversation",
        intro=None,
        suggestions=(),
        placeholder: str = "Type a message…",
        composer_label: str = "Your message",
        send_label: str = "Send",
        on_send=None,
        on_close=None,
        lang: str = "en",
    ) -> None:
        import wx
        import wx.html2 as webview

        self._wx = wx
        self.view = webview.WebView.New(parent)
        self.view.SetName(title)
        self._title = title
        self._lang = lang
        self._ready = False
        self._pending: list[tuple[str, object]] = []
        self._on_send = on_send
        self._on_close = on_close
        self._suggestions = list(suggestions)
        self._placeholder = placeholder
        self._composer_label = composer_label
        self._send_label = send_label
        self._want_focus = False

        intro_html = ""
        if intro is not None:
            intro_html = self._article_html(intro[0], intro[1])

        try:
            self.view.AddScriptMessageHandler("awv")
            self.view.Bind(webview.EVT_WEBVIEW_SCRIPT_MESSAGE_RECEIVED, self._on_script_message)
        except Exception:  # noqa: BLE001
            pass  # older backend: transcript renders, in-page composer won't post back
        self.view.Bind(webview.EVT_WEBVIEW_LOADED, self._on_loaded)
        self.view.SetPage(self._skeleton(intro_html), "")

    @property
    def control(self):
        return self.view

    # -- rendering ---------------------------------------------------------

    def _article_html(self, speaker: str, body_html: str) -> str:
        css_class = "you" if speaker.lower().startswith("you") else "other"
        return (
            f'<article class="{css_class}" aria-label="{html.escape(speaker)} message">'
            f"<h2>{html.escape(speaker)}</h2>{body_html}</article>"
        )

    def _suggestions_html(self) -> str:
        if not self._suggestions:
            return ""
        buttons = "".join(
            f'<button type="button" class="suggestion" data-prompt="{html.escape(s)}">'
            f"{html.escape(s)}</button>"
            for s in self._suggestions
        )
        return f'<div id="suggestions" role="group" aria-label="Suggestions">{buttons}</div>'

    def _skeleton(self, intro_html: str = "") -> str:
        ph = html.escape(self._placeholder)
        clabel = html.escape(self._composer_label)
        send = html.escape(self._send_label)
        # No landmark role / aria-label on the transcript: don't announce a
        # "region". ``aria-live`` still announces new turns; the reader moves by
        # heading (each turn is an <article> with a speaker <h2>).
        body = (
            '<div id="status" role="status" aria-live="assertive" class="visually-hidden"></div>'
            '<main id="log" aria-live="polite" tabindex="0">'
            f"\n{intro_html}\n</main>"
            f"{self._suggestions_html()}"
            '<form id="composer" autocomplete="off">'
            f'<label for="msg">{clabel}</label>'
            f'<textarea id="msg" rows="2" placeholder="{ph}" aria-label="{clabel}"></textarea>'
            f'<button type="submit" id="send">{send}</button>'
            "</form>"
        )
        scripts = """
  (function() {
    var log = document.getElementById('log');
    var sug = document.getElementById('suggestions');
    var form = document.getElementById('composer');
    var msg = document.getElementById('msg');
    function send(text) {
      text = (text || '').trim();
      if (!text) return;
      if (window.awv && window.awv.postMessage) {
        window.awv.postMessage(JSON.stringify({type: 'send', text: text}));
      }
    }
    form.addEventListener('submit', function(e) {
      e.preventDefault(); var t = msg.value; msg.value = ''; send(t);
    });
    msg.addEventListener('keydown', function(e) {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
    });
    document.addEventListener('keydown', function(e) {
      if (e.key === 'Escape') {
        e.preventDefault();
        if (window.awv && window.awv.postMessage) {
          window.awv.postMessage(JSON.stringify({type: 'close'}));
        }
      }
    });
    if (sug) {
      sug.addEventListener('click', function(e) {
        var b = e.target.closest('button');
        if (b) { send(b.getAttribute('data-prompt') || b.textContent); }
      });
    }
    window.__chat = {
      append: function(itemHtml) {
        var tmp = document.createElement('div'); tmp.innerHTML = itemHtml;
        while (tmp.firstChild) { log.appendChild(tmp.firstChild); }
        log.scrollTop = log.scrollHeight;
      },
      status: function(s) { var el = document.getElementById('status'); if (el) { el.textContent = s; } },
      hideSuggestions: function() { if (sug) { sug.hidden = true; } },
      focusInput: function() { msg.focus(); },
      setEnabled: function(on) {
        msg.disabled = !on; document.getElementById('send').disabled = !on;
        if (sug) { var bs = sug.querySelectorAll('button'); for (var i=0;i<bs.length;i++){ bs[i].disabled = !on; } }
      }
    };
  })();
"""
        return document(
            title=self._title, lang=self._lang, styles=_CHAT_STYLES, body=body, scripts=scripts
        )

    # -- bridge ------------------------------------------------------------

    def _on_script_message(self, event: object) -> None:
        try:
            data = json.loads(event.GetString())
        except Exception:  # noqa: BLE001
            return
        kind = data.get("type")
        if kind == "send" and self._on_send is not None:
            text = str(data.get("text", "")).strip()
            if text:
                self._on_send(text)
        elif kind == "close" and self._on_close is not None:
            self._on_close()

    def _on_loaded(self, _event: object) -> None:
        self._ready = True
        pending, self._pending = self._pending, []
        for kind, payload in pending:
            self._dispatch(kind, payload)
        if self._want_focus:
            self._want_focus = False
            self.view.SetFocus()
            self._run("window.__chat.focusInput();")

    def _dispatch(self, kind: str, payload: object) -> None:
        if kind == "append":
            self._run(f"window.__chat.append({json.dumps(payload)});")
        elif kind == "status":
            self._run(f"window.__chat.status({json.dumps(payload)});")
        elif kind == "hide":
            self._run("window.__chat.hideSuggestions();")
        elif kind == "enable":
            self._run(f"window.__chat.setEnabled({'true' if payload else 'false'});")

    def _do(self, kind: str, payload: object) -> None:
        if self._ready:
            self._dispatch(kind, payload)
        else:
            self._pending.append((kind, payload))

    # -- public API --------------------------------------------------------

    def append_message(self, speaker: str, body_html: str) -> None:
        """Append a turn. ``body_html`` is already-rendered HTML for the message."""
        self._do("append", self._article_html(speaker, body_html))

    def status(self, text: str) -> None:
        """Update the assertive status region (announced by screen readers)."""
        self._do("status", text)

    def hide_suggestions(self) -> None:
        self._do("hide", None)

    def set_input_enabled(self, enabled: bool) -> None:
        self._do("enable", enabled)

    def focus(self) -> None:
        """Move focus into the in-page message edit field."""
        self.view.SetFocus()
        if self._ready:
            self._run("window.__chat.focusInput();")
        else:
            self._want_focus = True

    def clear(self) -> None:
        self._ready = False
        self._pending = []
        self.view.SetPage(self._skeleton(), "")

    def _run(self, script: str) -> None:
        try:
            self.view.RunScript(script)
        except Exception:  # noqa: BLE001
            pass
