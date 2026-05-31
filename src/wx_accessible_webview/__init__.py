"""wx-accessible-webview — accessible ``wx.html2.WebView`` surfaces for wxPython.

Render HTML in a wxPython WebView that screen readers (NVDA *and* JAWS) read
correctly, by driving accessibility through semantic HTML/ARIA instead of the
native control.

Surfaces:

* :class:`AccessibleWebView` — embeddable content view (live region, status,
  JS bridge, Escape/F6 bridges, open-links-externally, text fallback).
* :class:`SidePreview` — live preview pane that updates in place.
* :class:`AccessibleHtmlDialog` — modal dialog with HTML body + real buttons;
  with :func:`show_message` and :func:`confirm` convenience helpers.
* :class:`AccessibleChatView` — chat surface with an in-page composer and
  suggestion chips.

All of this is a generalized extraction of the WebView stack built for Quill,
the screen-reader-first editor (a Community Access project).
"""

from __future__ import annotations

from wx_accessible_webview._common import DEFAULT_STYLES, strip_tags
from wx_accessible_webview.chat import AccessibleChatView
from wx_accessible_webview.dialog import AccessibleHtmlDialog, confirm, show_message
from wx_accessible_webview.webview import AccessibleWebView, SidePreview

__version__ = "0.2.0"
__all__ = [
    "AccessibleWebView",
    "SidePreview",
    "AccessibleHtmlDialog",
    "show_message",
    "confirm",
    "AccessibleChatView",
    "strip_tags",
    "DEFAULT_STYLES",
    "__version__",
]
