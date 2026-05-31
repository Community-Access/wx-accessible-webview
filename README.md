# wx-accessible-webview

An accessible wrapper around **`wx.html2.WebView`** for wxPython that renders web
content screen readers can actually read — verified in **NVDA *and* JAWS**.

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

- `AccessibleWebView(parent, *, title, lang="en", live_region=True, handler_name="awv", on_message=None, on_close=None, escape_to_close=False, initial_html="", styles=...)`
- `.control` — the underlying wx control (WebView, or the text fallback).
- `.using_webview` — `True` if a real WebView backend is in use.
- `.append(html_fragment)` — append HTML to the content area (announced if `live_region`).
- `.set_content(html_body)` — replace the content area.
- `.status(text)` — announce transient status (assertive region).
- `.focus()` — move focus into the content.
- `.run_js(script)` — run arbitrary JS in the page.

## Created by

Made by **Taylor Arndt** — it came out of building Quill, which needed an
accessible WebView and there wasn't a good one for wxPython. It's a **Community
Access** open-source project, and it's built to be contributed to.

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
