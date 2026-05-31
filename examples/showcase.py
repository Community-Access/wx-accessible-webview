"""Showcase: every accessible WebView surface in one small app.

A demo anyone can run to see what the library does:

  * an in-app **AccessibleWebView** rendering a document;
  * an **AccessibleHtmlDialog** (About box) with a link that opens in the browser;
  * a **confirm()** OK/Cancel dialog;
  * a live **SidePreview** is shown in `markdown_chat.py` / `live_preview` flows.

Run:
    python examples/showcase.py

Turn on a screen reader (NVDA / JAWS / VoiceOver) and tab around — the rendered
document reads as a real web page, the dialog announces its heading and buttons,
and the status line is announced when it changes.
"""

from __future__ import annotations

import wx

from wx_accessible_webview import AccessibleHtmlDialog, AccessibleWebView, confirm, show_message

DOCUMENT = """
<article>
  <h2>Welcome</h2>
  <p>This document is rendered inside a native <code>wx.html2.WebView</code> —
  and a screen reader reads it as a normal web page, because accessibility is
  driven by this <strong>HTML/ARIA</strong>, not the widget.</p>
  <h3>Try the buttons</h3>
  <ul>
    <li><em>About</em> — opens an accessible HTML dialog.</li>
    <li><em>Delete sample…</em> — an OK/Cancel confirm dialog.</li>
  </ul>
</article>
"""

ABOUT = """
<h2>wx-accessible-webview</h2>
<p>Accessible <code>wx.html2.WebView</code> surfaces for wxPython — verified in
<strong>NVDA</strong> and <strong>JAWS</strong>.</p>
<p>Born out of <strong>Quill</strong>, a Community Access project.
<a href="https://github.com/Community-Access/wx-accessible-webview">Project on GitHub</a>.</p>
<p>Press <kbd>Escape</kbd> or use a button to close.</p>
"""


def main() -> None:
    app = wx.App(False)
    frame = wx.Frame(None, title="wx-accessible-webview showcase", size=(720, 620))
    panel = wx.Panel(frame)
    sizer = wx.BoxSizer(wx.VERTICAL)

    doc = AccessibleWebView(
        panel,
        title="Document",
        live_region=False,  # it's a document, not a log
        open_links_externally=True,
        initial_html=DOCUMENT,
    )
    sizer.Add(doc.control, 1, wx.EXPAND | wx.ALL, 6)

    status = wx.StaticText(panel, label="Ready")
    sizer.Add(status, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

    row = wx.BoxSizer(wx.HORIZONTAL)
    about_btn = wx.Button(panel, label="&About")
    delete_btn = wx.Button(panel, label="&Delete sample…")
    row.Add(about_btn, 0, wx.RIGHT, 6)
    row.Add(delete_btn, 0)
    sizer.Add(row, 0, wx.ALL, 6)
    panel.SetSizer(sizer)

    def on_about(_evt):
        AccessibleHtmlDialog(
            frame, "About", ABOUT, [("Close", wx.ID_OK)], size=(560, 420)
        ).show_modal()

    def on_delete(_evt):
        if confirm(
            frame,
            "Delete sample?",
            "<h2>Delete the sample?</h2><p>This can't be undone in the demo "
            "(it just updates the status line).</p>",
            ok_label="Delete",
        ):
            status.SetLabel("Deleted.")
            doc.set_content("<article><h2>Gone</h2><p>The sample was deleted.</p></article>")
            show_message(frame, "Done", "<p>Sample deleted.</p>")
        else:
            status.SetLabel("Cancelled — nothing deleted.")

    about_btn.Bind(wx.EVT_BUTTON, on_about)
    delete_btn.Bind(wx.EVT_BUTTON, on_delete)

    frame.Show()
    wx.CallAfter(doc.focus)
    app.MainLoop()


if __name__ == "__main__":
    main()
