"""wx-accessible-webview — an accessible wx.html2.WebView wrapper.

Render HTML in a wxPython WebView that screen readers (NVDA *and* JAWS) read
correctly, by driving accessibility through semantic HTML/ARIA instead of the
native control.
"""
from __future__ import annotations

from wx_accessible_webview.webview import AccessibleWebView, strip_tags

__version__ = "0.1.0"
__all__ = ["AccessibleWebView", "strip_tags", "__version__"]
