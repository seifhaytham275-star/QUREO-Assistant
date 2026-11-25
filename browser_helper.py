"""QUREO browser control (Playwright + Microsoft Edge).

IMPORTANT: Playwright's sync API is bound to the thread that created it.
`QureoBrowser` therefore runs every call on ONE dedicated worker thread via
`call()`; the GUI must never touch Playwright objects directly.

The selectors below are heuristics (QUREO's markup is not under our control).
They are collected at the top so they are easy to adjust.
"""
import os
import re
import time
import hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from playwright.sync_api import sync_playwright

import chapter_guard

START_URL = os.environ.get("QUREO_START_URL", "https://me-tp.qureo.education/course/javascript_en")

# --- tunable heuristics ----------------------------------------------------
CHECK_RE = re.compile(r"^\s*(check( answer)?|submit( answer)?|run( code)?|verify|test)\s*$", re.I)
NEXT_RE = re.compile(r"^\s*(next( lesson| exercise| page| step)?|continue|proceed)\b", re.I)
RESUME_RE = re.compile(r"(continue|resume|pick up|keep going|start next)", re.I)
LOGIN_LINK_RE = re.compile(r"^\s*(log ?in|sign ?in)\s*$", re.I)
ASSESSMENT_RE = re.compile(
    r"\b(final (exam|assessment|test|quiz)|exam|graded (quiz|test|assignment|assessment)|assessment|"
    r"chapter (test|exam)|unit test|midterm)\b", re.I)
# Phrases in the page body that signal a graded/limited attempt (conservative: pause).
ASSESSMENT_TEXT_RE = re.compile(
    r"(this (test|quiz|exam) is graded|counts (toward|towards) your (grade|score)|"
    r"you (only )?have (one|1|\d+) attempts?|time limit|timed (exam|test|quiz))", re.I)
CAPTCHA_SELECTORS = [
    "iframe[src*='recaptcha']", "iframe[src*='hcaptcha']", "iframe[src*='turnstile']",
    ".g-recaptcha", ".h-captcha", "[class*='captcha' i]",
]
MANUAL_AUTH_TEXT = re.compile(
    r"(captcha|i'?m not a robot|verification code|verify your (email|identity)|"
    r"two[- ]factor|2fa|enter the code|check your email)", re.I)
ACCEPT_RE = re.compile(r"\b(correct|well done|great job|success(ful)?|passed|nice work|that'?s right|all tests passed)\b", re.I)
REJECT_RE = re.compile(r"\b(incorrect|try again|wrong|not quite|failed|error|doesn'?t match|did not pass|missing)\b", re.I)
HEADING_SELECTORS = (
    "h1, h2, [class*='breadcrumb' i], [aria-label*='breadcrumb' i], "
    "[class*='chapter-title' i], [class*='chapterTitle' i], [data-chapter], "
    "[aria-current='page'], [aria-current='true'], li.active, a.active"
)
EDITOR_SELECTORS = [
    ".monaco-editor", ".CodeMirror", ".cm-editor", ".ace_editor",
    "textarea[class*='code' i], textarea[class*='editor' i]",
]


def profile_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
    p = Path(base) / "QUREO-Assistant" / "edge-profile"
    p.mkdir(parents=True, exist_ok=True)
    return p


class QureoBrowser:
    def __init__(self):
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="playwright")
        self._pw = None
        self._ctx = None
        self.page = None

    # ---- threading helper ------------------------------------------------
    def call(self, fn, *args, **kw):
        """Run fn on the Playwright thread and return its result (blocking)."""
        return self._pool.submit(fn, *args, **kw).result()

    def submit(self, fn, *args, **kw):
        return self._pool.submit(fn, *args, **kw)

    # ---- lifecycle (call these through call()/submit()) -------------------
    def open(self, url=START_URL):
        if self.page and not self.page.is_closed():
            self.page.bring_to_front()
            return
        self._pw = sync_playwright().start()
        channel = os.environ.get("QUREO_BROWSER_CHANNEL", "msedge")
        kw = dict(headless=os.environ.get("QUREO_HEADLESS") == "1", viewport=None if os.environ.get("QUREO_HEADLESS") != "1" else {"width": 1280, "height": 900})
        if channel != "chromium":
            kw["channel"] = channel
        try:
            if os.environ.get("QUREO_TEMP_PROFILE") == "1":
                self._browser = self._pw.chromium.launch(**{k: v for k, v in kw.items() if k != "viewport"})
                self._ctx = self._browser.new_context()
            else:
                self._ctx = self._pw.chromium.launch_persistent_context(str(profile_dir()), **kw)
        except Exception as e:
            self._pw.stop(); self._pw = None
            raise RuntimeError("Microsoft Edge could not be started. Install/update Edge and try again.") from e
        self._ctx.set_default_timeout(15000)
        self.page = self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()
        self._install_chapter_block()
        self.page.goto(url, wait_until="domcontentloaded")

    def _install_chapter_block(self):
        """Hard network-level block on URLs that clearly name a chapter > 17."""
        def handler(route):
            u = route.request.url
            if route.request.resource_type == "document" and chapter_guard.target_is_forbidden("", u):
                route.abort()
            else:
                route.continue_()
        self._ctx.route("**/*", handler)

    def close(self):
        try:
            if self._ctx:
                self._ctx.close()
            if getattr(self, "_browser", None):
                self._browser.close()
        finally:
            self._ctx = self.page = None
            if self._pw:
                self._pw.stop()
            self._pw = None

    def alive(self):
        return bool(self.page and not self.page.is_closed())

    # ---- reading ----------------------------------------------------------
    def settle(self, ms=1200):
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=10000)
        except Exception:
            pass
        self.page.wait_for_timeout(ms)

    def heading_text(self):
        parts = []
        try:
            for el in self.page.locator(HEADING_SELECTORS).all()[:40]:
                try:
                    if el.is_visible():
                        t = el.inner_text(timeout=1000).strip()
                        if t:
                            parts.append(t[:200])
                except Exception:
                    pass
        except Exception:
            pass
        return "\n".join(parts)

    def snapshot(self):
        p = self.page
        try:
            body = p.locator("body").inner_text(timeout=10000)
        except Exception:
            body = ""
        return {
            "url": p.url, "title": p.title(), "heading": self.heading_text(),
            "text": body[:14000],
            "sig": hashlib.md5((p.url + body[:4000]).encode("utf-8", "ignore")).hexdigest(),
        }

    def chapter(self, snap=None):
        s = snap or self.snapshot()
        return chapter_guard.read_chapter(s["heading"], s["url"], s["title"])

    # ---- login ------------------------------------------------------------
    def needs_manual_auth(self):
        for sel in CAPTCHA_SELECTORS:
            try:
                if self.page.locator(sel).first.is_visible(timeout=300):
                    return True
            except Exception:
                pass
        try:
            return bool(MANUAL_AUTH_TEXT.search(self.page.locator("body").inner_text(timeout=3000)[:6000]))
        except Exception:
            return False

    def _visible(self, selector):
        loc = self.page.locator(selector)
        for i in range(min(loc.count(), 10)):
            el = loc.nth(i)
            try:
                if el.is_visible():
                    return el
            except Exception:
                pass
        return None

    def try_login(self, username, password):
        """Fill the sign-in form with the user's own credentials.

        Returns 'logged_in', 'needs_manual', or 'no_form'. The password is only
        passed to Playwright's fill(); it is never logged or stored here.
        """
        pw_sel = "input[type='password']"
        user_sel = ("input[type='email'], input[autocomplete='username'], input[name*='user' i], "
                    "input[name*='email' i], input[id*='email' i], input[id*='user' i], input[type='text']")
        if not self._visible(pw_sel) and not self._visible(user_sel):
            link = self.page.get_by_role("link", name=LOGIN_LINK_RE).first
            btn = self.page.get_by_role("button", name=LOGIN_LINK_RE).first
            for cand in (link, btn):
                try:
                    if cand.is_visible(timeout=500):
                        cand.click(); self.settle(); break
                except Exception:
                    pass
        if self.needs_manual_auth():
            return "needs_manual"
        u = self._visible(user_sel)
        pwf = self._visible(pw_sel)
        if not u and not pwf:
            return "no_form"
        if u:
            u.fill(username)
        if not pwf:                       # two-step flow: email first
            if u:
                u.press("Enter")
            self.settle(1500)
            pwf = self._visible(pw_sel)
        if not pwf:
            return "needs_manual" if self.needs_manual_auth() else "no_form"
        pwf.fill(password)
        pwf.press("Enter")
        self.settle(2500)
        if self.needs_manual_auth():
            return "needs_manual"
        if self._visible(pw_sel):
            return "needs_manual"         # still on the form: wrong password / extra step
        return "logged_in"

    # ---- page classification ---------------------------------------------
    def _editors(self):
        found = []
        for sel in EDITOR_SELECTORS:
            loc = self.page.locator(sel)
            for i in range(loc.count()):
                try:
                    if loc.nth(i).is_visible():
                        found.append((sel, i))
                except Exception:
                    pass
            if found:
                break
        return found

    def _choices(self):
        return self.page.locator("input[type='radio']:visible, input[type='checkbox']:visible")

    def _blanks(self):
        loc = self.page.locator("input[type='text']:visible, input:not([type]):visible")
        return [loc.nth(i) for i in range(loc.count())
                if (loc.nth(i).get_attribute("type") or "text") == "text"
                and not re.search(r"search|user|email|pass", (loc.nth(i).get_attribute("name") or "") + (loc.nth(i).get_attribute("id") or ""), re.I)]

    def _button(self, regex):
        for role in ("button", "link"):
            loc = self.page.get_by_role(role, name=regex)
            for i in range(min(loc.count(), 6)):
                el = loc.nth(i)
                try:
                    if el.is_visible():
                        return el
                except Exception:
                    pass
        return None

    def classify(self, snap):
        """'assessment' | 'exercise' | 'lesson'  (assessment wins: be conservative)."""
        label = f"{snap['heading']}\n{snap['title']}\n{snap['url']}"
        if ASSESSMENT_RE.search(label) or ASSESSMENT_TEXT_RE.search(snap["text"][:4000]):
            return "assessment"
        has_input = bool(self._editors() or self._choices().count() or self._blanks())
        if has_input and self._button(CHECK_RE):
            return "exercise"
        return "lesson"

    # ---- answering ------------------------------------------------------
    def apply_answer(self, solution):
        kind, ans = solution.get("type"), solution.get("answer")
        if kind == "multiple_choice":
            return self._pick_choice(str(ans))
        if kind == "fill_blank":
            vals = ans if isinstance(ans, list) else [ans]
            blanks = self._blanks()
            if not blanks:
                return False
            for el, v in zip(blanks, vals):
                el.fill(str(v))
            return True
        if kind == "code":
            return self._fill_code(ans)
        return False

    def _pick_choice(self, ans):
        a = ans.strip().lower()
        loc = self._choices()
        labels = []
        for i in range(loc.count()):
            el = loc.nth(i)
            txt = ""
            try:
                txt = el.evaluate("e => (e.labels && e.labels[0] ? e.labels[0].innerText : e.parentElement.innerText) || ''")
            except Exception:
                pass
            labels.append((el, txt.strip().lower()))
        pick = None
        if len(a) == 1 and a.isalpha():
            idx = ord(a) - 97
            if 0 <= idx < len(labels):
                pick = labels[idx][0]
        if pick is None:
            for el, t in labels:
                if t and (t == a or a in t or t in a):
                    pick = el; break
        if pick is None:
            return False
        pick.check(force=True)
        return True

    def _fill_code(self, code):
        eds = self._editors()
        if isinstance(code, dict):
            code = "\n".join(str(v) for v in code.values())
        code = str(code)
        if not eds:
            return False
        sel, i = eds[0]
        target = self.page.locator(sel).nth(i)
        if sel.startswith("textarea"):
            target.fill(code); return True
        js_set = """(code) => {
          try { if (window.monaco) { const m = window.monaco.editor.getModels()[0]; m.setValue(code); return true; } } catch (e) {}
          try { const cm = document.querySelector('.CodeMirror'); if (cm && cm.CodeMirror) { cm.CodeMirror.setValue(code); return true; } } catch (e) {}
          try { if (window.ace) { const el = document.querySelector('.ace_editor'); window.ace.edit(el).setValue(code, -1); return true; } } catch (e) {}
          return false; }"""
        try:
            if self.page.evaluate(js_set, code):
                return True
        except Exception:
            pass
        target.click()
        self.page.keyboard.press("Control+A")
        self.page.keyboard.press("Delete")
        self.page.keyboard.insert_text(code)
        return True

    def click_check(self):
        btn = self._button(CHECK_RE)
        if not btn:
            return False
        btn.click()
        self.settle(1800)
        return True

    def read_feedback(self):
        """Return ('accepted'|'rejected'|'unknown', feedback_text)."""
        texts = []
        try:
            loc = self.page.locator(
                "[class*='feedback' i], [class*='result' i], [class*='success' i], [class*='error' i], "
                "[class*='alert' i], [role='alert'], [role='status'], [class*='toast' i]")
            for i in range(min(loc.count(), 12)):
                el = loc.nth(i)
                if el.is_visible():
                    t = el.inner_text(timeout=800).strip()
                    if t:
                        texts.append(t[:500])
        except Exception:
            pass
        fb = "\n".join(dict.fromkeys(texts))
        if not fb:
            return "unknown", ""
        if REJECT_RE.search(fb):
            return "rejected", fb
        if ACCEPT_RE.search(fb):
            return "accepted", fb
        return "unknown", fb

    # ---- navigation -----------------------------------------------------
    def next_target(self):
        """Return (locator, label, href) for the Next/Continue control, or None."""
        btn = self._button(NEXT_RE)
        if not btn:
            return None
        try:
            label = (btn.inner_text(timeout=800) or "").strip()
        except Exception:
            label = ""
        href = btn.get_attribute("href") or ""
        return btn, label, href

    def click_next(self):
        t = self.next_target()
        if not t:
            return False
        t[0].click()
        self.settle()
        return True

    def resume_course(self):
        """From a dashboard/home page, press the platform's own continue/resume control."""
        btn = self._button(RESUME_RE)
        if not btn:
            return False
        try:
            if chapter_guard.target_is_forbidden(btn.inner_text(timeout=800), btn.get_attribute("href") or ""):
                return False
        except Exception:
            pass
        btn.click(); self.settle(1500)
        return True

    def go_back(self):
        try:
            self.page.go_back(wait_until="domcontentloaded")
        except Exception:
            pass
