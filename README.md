# wx-accessible-webview

Accessible **`wx.html2.WebView`** surfaces for wxPython — render web content
screen readers can actually read, verified in **NVDA *and* JAWS**.

One small toolkit covering every WebView surface a real app needs:

- **`AccessibleWebView`** — an embeddable content view (live region, status, JS
  bridge, Escape/F6 key bridges, open-links-in-browser, text fallback);
- **`SidePreview`** — a live preview pane that updates in place as you type;
- **`AccessibleHtmlDialog`** — a modal dialog with an HTML body and real wx
  buttons (plus `show_message` / `confirm` helpers);
- **`AccessibleChatView`** — a chat surface with an in-page composer and
  suggestion chips.

## The problem

`wx.html2.WebView` is a factory-created **native** control (Edge **WebView2** on
Windows, WKWebView on macOS, WebKitGTK on Linux). Because it's native and
factory-built, you **can't meaningfully subclass it** to fix accessibility — and
embedded in a wxPython app it reads inconsistently in NVDA and often **not at all
in JAWS**. This has blocked accessible rich/HTML content (Markdown, chat,
previews) in wxPython apps for years.

## The idea

A WebView's accessibility is driven by the **HTML you render into it**, not by
the wx widget. So instead of fighting the control, render a **semantic,
screen-reader-friendly document** — and the screen reader follows it like any web
page.

`AccessibleWebView` gives you:

- a semantic page — `lang`, viewport, readable + high-contrast / `forced-colors` CSS;
- an optional **ARIA live region** (`role="log" aria-live="polite"`) so appended
  content is announced automatically;
- an assertive `role="status"` region for transient announcements;
- a **JS→Python bridge** (`window.<name>.post(...)`) so the page can send events back;
- optional **Escape-to-close**, bridged out of the native control (which swallows it);
- focus management into the content;
- a graceful **read-only text fallback** when no WebView backend is present.

## Install

```bash
pip install wx-accessible-webview
```

(Requires wxPython 4.2+.)

## Usage

```python
import wx
from wx_accessible_webview import AccessibleWebView

app = wx.App()
frame = wx.Frame(None, title="Demo")

view = AccessibleWebView(
    frame,
    title="Conversation",
    live_region=True,            # appended content is announced
    handler_name="demo",         # window.demo.postMessage(...)
    on_message=lambda data: print("from page:", data),
    escape_to_close=True,
    on_close=lambda: frame.Close(),
)

sizer = wx.BoxSizer(wx.VERTICAL)
sizer.Add(view.control, 1, wx.EXPAND)
frame.SetSizer(sizer)

view.append("<article><h2>Quill</h2><p>Hi! New messages are announced.</p></article>")
view.status("Ready")
frame.Show()
app.MainLoop()
```

Render Markdown by converting it to HTML yourself (any Markdown library) and
passing the result to `append()` / `set_content()` — this package stays
dependency-light (just wxPython) and leaves rendering choices to you.

## API

### `AccessibleWebView` — embeddable content view
`AccessibleWebView(parent, *, title, lang="en", live_region=True, handler_name="awv", on_message=None, on_close=None, on_return=None, escape_to_close=False, open_links_externally=False, initial_html="", styles=...)`

- `.control` — the underlying wx control (WebView, or the text fallback).
- `.using_webview` — `True` if a real WebView backend is in use.
- `.append(html_fragment)` — append HTML to the content area (announced if `live_region`).
- `.set_content(html_body)` — replace the content area.
- `.status(text)` — announce transient status (assertive region).
- `.clear()` — reset to an empty document.
- `.focus()` — move focus into the content.
- `.run_js(script)` — run arbitrary JS in the page.

`on_return` (Escape **or F6**) is handy for handing focus back from a preview
pane to an editor; `open_links_externally` opens `http(s)` links in the system
browser instead of navigating the embedded view.

### `SidePreview` — live preview pane
`SidePreview(parent, *, title="Preview", lang="en", on_return=None, open_links_externally=True, styles=...)`

- `.update(body_html)` — replace the body in place (scroll/SR position preserved).
- `.control`, `.focus()`.

### `AccessibleHtmlDialog` — modal dialog
`AccessibleHtmlDialog(parent, title, body_html, buttons=None, *, size=(640, 560), open_links_externally=True, lang="en", styles=...)`

- `buttons` — list of `(label, return_id)`; the last is the default. Defaults to a single **Close** button.
- `.show_modal() -> int` — returns the chosen button id (or `wx.ID_CANCEL` on Escape/close).
- Helpers: `show_message(parent, title, body_html, ...)` (one button) and
  `confirm(parent, title, body_html, ...) -> bool` (OK/Cancel).

### `AccessibleChatView` — chat surface
`AccessibleChatView(parent, *, title="Conversation", intro=None, suggestions=(), placeholder=..., composer_label=..., send_label="Send", on_send=None, on_close=None, lang="en")`

- `.append_message(speaker, body_html)` — add a turn (announced via live region).
- `.status(text)`, `.hide_suggestions()`, `.set_input_enabled(enabled)`, `.focus()`, `.clear()`.

The transcript, suggestion chips, **and** the message edit field all live inside
one accessible page; Enter sends, Shift+Enter inserts a newline, suggestions hide
after the first message (like Apple Intelligence).

### Examples

- `examples/demo.py` — the minimal content view.
- `examples/showcase.py` — content view + `AccessibleHtmlDialog` + `confirm`.
- `examples/markdown_chat.py` — a full `AccessibleChatView` Markdown chat.

## Born out of Quill

This came out of building **Quill** — the screen-reader-first writing and
document environment (a Community Access project).

Accessible embedded web content in wxPython is a problem people had been
chipping at for **years**. The usual experience: it'd *sometimes* read in NVDA,
and **basically never in JAWS** — JAWS just wouldn't treat the embedded WebView
as a real web document. It had eaten a lot of hours across a lot of attempts.

Quill needed it badly — the AI chat emits Markdown (headings, lists, code), so it
wanted real HTML, which meant the WebView, which meant the wall. Rather than keep
fighting the native control, the breakthrough was to stop trying to "fix" the
widget and instead drive accessibility entirely through the **HTML/ARIA rendered
into it** — and that finally read correctly in **NVDA *and* JAWS**.

So after a lot of tries, we got it working. This library is that solution, broken
out so the whole wxPython community can use it. In Quill it now powers the AI
chat, the Markdown/HTML preview, the About dialog, and the update dialogs.

## Created by

Made by **Taylor Arndt**, a **Community Access** open-source project — built to be
contributed to.

## Contributing

**Anyone can contribute — and we want you to.** Bug reports, features, docs, and
especially **screen-reader testing** (NVDA / JAWS / Narrator / VoiceOver / Orca)
are all welcome. Open an issue or a pull request — see `CONTRIBUTING.md`.

## Contributors

Everyone who contributes is recognized here automatically:

[![Contributors](https://contrib.rocks/image?repo=Community-Access/wx-accessible-webview)](https://github.com/Community-Access/wx-accessible-webview/graphs/contributors)

<sub>Contributor image via <a href="https://contrib.rocks">contrib.rocks</a>.</sub>

## License

MIT.
