"""Minimal demo of AccessibleWebView.

Run:  python examples/demo.py
A small window with an accessible WebView; type in the box and press Enter to
append an announced "message". Escape closes. Try it with NVDA or JAWS.
"""
from __future__ import annotations

import html

import wx

from wx_accessible_webview import AccessibleWebView


def main() -> None:
    app = wx.App(False)
    frame = wx.Frame(None, title="AccessibleWebView demo", size=(640, 560))
    panel = wx.Panel(frame)
    sizer = wx.BoxSizer(wx.VERTICAL)

    view = AccessibleWebView(
        panel,
        title="Conversation",
        live_region=True,
        handler_name="demo",
        on_message=lambda data: print("message from page:", data),
        escape_to_close=True,
        on_close=frame.Close,
        initial_html="<article><h2>Demo</h2><p>New messages are announced. "
        "Type below and press Enter.</p></article>",
    )
    sizer.Add(view.control, 1, wx.EXPAND | wx.ALL, 6)

    row = wx.BoxSizer(wx.HORIZONTAL)
    entry = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
    entry.SetName("Message")
    send = wx.Button(panel, label="Send")
    row.Add(entry, 1, wx.EXPAND | wx.RIGHT, 6)
    row.Add(send, 0)
    sizer.Add(row, 0, wx.EXPAND | wx.ALL, 6)
    panel.SetSizer(sizer)

    def submit(_event=None) -> None:
        text = entry.GetValue().strip()
        if not text:
            return
        view.append(f"<article><h2>You</h2><p>{html.escape(text)}</p></article>")
        view.status("Message sent")
        entry.SetValue("")
        entry.SetFocus()

    entry.Bind(wx.EVT_TEXT_ENTER, submit)
    send.Bind(wx.EVT_BUTTON, submit)

    frame.Show()
    wx.CallAfter(view.focus)
    app.MainLoop()


if __name__ == "__main__":
    main()
