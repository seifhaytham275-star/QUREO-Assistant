"""Local, user-controlled QUREO browser helper.

Opens Microsoft Edge using Playwright. The user signs in directly in the browser.
Only visible page text is read; this module never clicks answer/submit controls.
"""
from playwright.sync_api import sync_playwright

_playwright = None
_browser = None
_page = None

def open_qureo():
    global _playwright, _browser, _page
    if _page and not _page.is_closed():
        _page.bring_to_front()
        return _page
    _playwright = sync_playwright().start()
    try:
        _browser = _playwright.chromium.launch(channel="msedge", headless=False)
    except Exception:
        _playwright.stop()
        _playwright = None
        raise RuntimeError("Microsoft Edge was not found. Install/update Edge, then try again.")
    _page = _browser.new_page()
    _page.goto("https://qureo.com/", wait_until="domcontentloaded")
    return _page

def read_visible_page():
    if not _page or _page.is_closed():
        raise RuntimeError("Open QUREO first, then sign in and open an exercise.")
    text = _page.locator("body").inner_text(timeout=10000)
    return text[:14000]

def close_browser():
    global _playwright, _browser, _page
    try:
        if _browser:
            _browser.close()
    finally:
        _browser = _page = None
        if _playwright:
            _playwright.stop()
        _playwright = None
