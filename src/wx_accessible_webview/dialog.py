"""Accessible modal dialogs whose body renders as HTML in a ``wx.html2.WebView``.

The same accessible-WebView trick used for embedded views works for modals:
render a semantic HTML document into the WebView so screen readers read it as a
web page, give the dialog a real row of wx buttons (so focus, default-button,
and Enter behave natively), bridge Escape out of the native control to cancel,
and open ``http(s)`` links in the system browser.

* :class:`AccessibleHtmlDialog` — HTML body + a configurable row of buttons;
  :meth:`AccessibleHtmlDialog.show_modal` returns the chosen button id.
* :func:`show_message` — one-button informational dialog.
* :func:`confirm` — two-button OK/Cancel (returns ``True``/``False``).

This generalizes Quill's ``HtmlMessageDialog`` (used for its About box and the
update dialogs).
"""

from __future__ import annotations

import json

from wx_accessible_webview._common import (
    DEFAULT_STYLES,
    document,
    key_bridge_js,
    strip_tags,
)


class AccessibleHtmlDialog:
    """A modal dialog with an HTML body and a configurable row of buttons.

    Parameters
    ----------
    parent:
        The parent wx window (may be ``None``).
    title:
        Dialog title and accessible name.
    body_html:
        HTML fragment rendered into the WebView body.
    buttons:
        Sequence of ``(label, return_id)`` pairs. The last button is the
        default. If omitted, a single "Close" button (``wx.ID_CANCEL``) is used.
    size:
        Initial ``(width, height)``.
    open_links_externally:
        Open ``http(s)`` links in the system browser (default True).
    lang / styles:
        Document language and CSS.

    :meth:`show_modal` returns the chosen button id, or ``wx.ID_CANCEL`` on
    Escape / window close.
    """

    def __init__(
        self,
        parent,
        title: str,
        body_html: str,
        buttons=None,
        *,
        size=(640, 560),
        open_links_externally: bool = True,
        lang: str = "en",
        styles: str = DEFAULT_STYLES,
    ) -> None:
        import wx

        self._wx = wx
        self._result = wx.ID_CANCEL
        self._ready = False
        self._open_links_externally = open_links_externally
        self.view = None
        self._fallback = None

        if not buttons:
            buttons = [("Close", wx.ID_CANCEL)]

        self.dialog = wx.Dialog(
            parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )
        self.dialog.SetName(title)
        self.dialog.SetSize(size)
        outer = wx.BoxSizer(wx.VERTICAL)

        page = document(
            title=title,
            lang=lang,
            styles=styles,
            body=f'<main id="content" tabindex="-1">\n{body_html}\n</main>',
            scripts=key_bridge_js("awv", {"Escape": "__close"}),
        )

        try:
            import wx.html2 as webview

            self.view = webview.WebView.New(self.dialog)
            self.view.SetName(title)
            self.view.Bind(webview.EVT_WEBVIEW_LOADED, self._on_loaded)
            if open_links_externally:
                self.view.Bind(webview.EVT_WEBVIEW_NAVIGATING, self._on_navigating)
            try:
                self.view.AddScriptMessageHandler("awv")
                self.view.Bind(webview.EVT_WEBVIEW_SCRIPT_MESSAGE_RECEIVED, self._on_script_message)
            except Exception:  # noqa: BLE001
                pass
            self.view.SetPage(page, "")
            outer.Add(self.view, 1, wx.EXPAND)
        except Exception:  # noqa: BLE001
            self.view = None
            self._fallback = wx.TextCtrl(
                self.dialog, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2
            )
            self._fallback.SetName(title)
            self._fallback.SetValue(strip_tags(body_html))
            outer.Add(self._fallback, 1, wx.EXPAND | wx.ALL, 8)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.AddStretchSpacer()
        buttons = list(buttons)
        for index, (label, return_id) in enumerate(buttons):
            button = wx.Button(self.dialog, return_id, label=label)
            if index == len(buttons) - 1:
                button.SetDefault()
            button.Bind(wx.EVT_BUTTON, lambda _e, r=return_id: self._end(r))
            row.Add(button, 0, wx.LEFT, 8)
        outer.Add(row, 0, wx.EXPAND | wx.ALL, 12)

        self.dialog.SetSizer(outer)
        self.dialog.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)

    def _on_loaded(self, _event: object) -> None:
        self._ready = True

    def _on_navigating(self, event: object) -> None:
        url = event.GetURL() or ""
        if self._ready and url.startswith(("http://", "https://")):
            event.Veto()
            import webbrowser

            webbrowser.open(url)

    def _on_char_hook(self, event: object) -> None:
        if event.GetKeyCode() == self._wx.WXK_ESCAPE:
            self._end(self._wx.ID_CANCEL)
            return
        event.Skip()

    def _on_script_message(self, event: object) -> None:
        try:
            data = json.loads(event.GetString())
        except Exception:  # noqa: BLE001
            return
        if data.get("type") == "__close":
            self._end(self._wx.ID_CANCEL)

    def _end(self, return_id: int) -> None:
        self._result = return_id
        self.dialog.EndModal(return_id)

    def show_modal(self) -> int:
        """Show the dialog modally; returns the chosen button id."""
        self.dialog.CentreOnParent()
        try:
            self._wx.CallAfter(self._focus)
            self.dialog.ShowModal()
        finally:
            self.dialog.Destroy()
        return self._result

    def _focus(self) -> None:
        if self.view is not None:
            self.view.SetFocus()
        elif self._fallback is not None:
            self._fallback.SetFocus()


def show_message(
    parent,
    title: str,
    body_html: str,
    *,
    button_label: str = "Close",
    **kwargs,
) -> None:
    """Show a one-button informational HTML dialog."""
    import wx

    AccessibleHtmlDialog(
        parent, title, body_html, [(button_label, wx.ID_OK)], **kwargs
    ).show_modal()


def confirm(
    parent,
    title: str,
    body_html: str,
    *,
    ok_label: str = "OK",
    cancel_label: str = "Cancel",
    **kwargs,
) -> bool:
    """Show an OK/Cancel HTML dialog; returns ``True`` if the user confirmed."""
    import wx

    result = AccessibleHtmlDialog(
        parent,
        title,
        body_html,
        [(cancel_label, wx.ID_CANCEL), (ok_label, wx.ID_OK)],
        **kwargs,
    ).show_modal()
    return result == wx.ID_OK
