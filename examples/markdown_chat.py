"""An accessible Markdown chat, using AccessibleChatView.

This mirrors how Quill uses the library — the AI emits Markdown, you render it
to HTML, and the in-page composer + live region announce each new turn in
NVDA / JAWS. The whole conversation (transcript, suggestion chips, and the
message field) lives inside one accessible WebView document.

Run:
    pip install -e ".[examples]"   # gets the `markdown` renderer (optional)
    python examples/markdown_chat.py

If `markdown` isn't installed it still runs, using a tiny built-in fallback
renderer, so the example never hard-depends on anything beyond wxPython.
"""

from __future__ import annotations

import html

import wx

from wx_accessible_webview import AccessibleChatView

try:  # optional: nicer rendering if the user installed the extra
    import markdown as _markdown

    def render_markdown(text: str) -> str:
        return _markdown.markdown(text, extensions=["fenced_code", "tables"])
except ImportError:  # dependency-light fallback — paragraphs + inline code/bold
    import re

    def render_markdown(text: str) -> str:
        out: list[str] = []
        for block in text.split("\n\n"):
            block = block.strip()
            if not block:
                continue
            if block.startswith("# "):
                out.append(f"<h2>{html.escape(block[2:])}</h2>")
                continue
            esc = html.escape(block)
            esc = re.sub(r"`([^`]+)`", r"<code>\1</code>", esc)
            esc = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", esc)
            out.append(f"<p>{esc.replace(chr(10), '<br>')}</p>")
        return "\n".join(out)


def _fake_reply(prompt: str) -> str:
    """Stand-in for a real model — echoes Markdown so you can see it render."""
    return (
        f"You said: **{prompt}**\n\n"
        "Here's some Markdown so you can hear it announced:\n\n"
        "# A heading\n\n"
        "And a little `inline code` plus **bold** text."
    )


def main() -> None:
    app = wx.App(False)
    frame = wx.Frame(None, title="Accessible Markdown chat", size=(680, 640))
    panel = wx.Panel(frame)
    sizer = wx.BoxSizer(wx.VERTICAL)

    chat = AccessibleChatView(
        panel,
        title="Conversation",
        intro=(
            "Assistant",
            render_markdown(
                "Hi! Type a message below and press **Enter**. New turns are "
                "announced in your screen reader. Press `Escape` to close."
            ),
        ),
        suggestions=("Summarize this", "Make it formal", "Translate to French"),
        placeholder="Ask anything…",
        on_send=lambda text: on_send(text),
        on_close=frame.Close,
    )
    sizer.Add(chat.control, 1, wx.EXPAND | wx.ALL, 6)
    panel.SetSizer(sizer)

    def on_send(text: str) -> None:
        chat.hide_suggestions()
        chat.append_message("You", render_markdown(text))
        chat.status("Thinking…")
        # A real app would call a model off-thread; here we reply inline.
        chat.append_message("Assistant", render_markdown(_fake_reply(text)))
        chat.status("Reply ready")

    frame.Show()
    wx.CallAfter(chat.focus)
    app.MainLoop()


if __name__ == "__main__":
    main()
