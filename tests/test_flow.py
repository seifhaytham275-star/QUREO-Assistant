"""End-to-end test of the real automation loop in Chromium against tests/mock_site.py.

Uses a fake AI (no network). Run:  QUREO_BROWSER_CHANNEL=chromium pytest tests -q
"""
import os, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.dirname(__file__))

os.environ.update(QUREO_BROWSER_CHANNEL="chromium", QUREO_HEADLESS="1", QUREO_TEMP_PROFILE="1")

import pytest
import ai_solver, chapter_guard
import mock_site
from automation import Automation
from browser_helper import QureoBrowser


@pytest.fixture
def env(monkeypatch):
    calls = {"solve": 0, "explain": 0, "wrong_first": 0}

    def fake_solve(key, model, text, feedback="", attempt=1):
        calls["solve"] += 1
        if "Which keyword declares a constant" in text:
            return {"type": "multiple_choice", "answer": "const", "explanation": "const declares constants"}
        # Chapter 15's code exercise: first attempt deliberately wrong to exercise the retry path
        if "Chapter 15: Practice" in text and attempt == 1:
            calls["wrong_first"] += 1
            return {"type": "code", "answer": "alert('hi')", "explanation": "first try"}
        return {"type": "code", "answer": "console.log('hi');", "explanation": "prints hi"}

    def fake_explain(key, model, text):
        calls["explain"] += 1
        return "DOM = Document Object Model"

    monkeypatch.setattr(ai_solver, "solve", fake_solve)
    monkeypatch.setattr(ai_solver, "explain", fake_explain)
    yield calls


def run_auto(base, start_url, js_last=False, on_pause=None, timeout=90):
    b = QureoBrowser()
    logs, done = [], {}
    auto = Automation(b, lambda: "k", lambda: "m", logs.append, lambda ch, s: None,
                      lambda msg, ok: done.update(msg=msg, ok=ok))
    b.call(b.open, start_url)
    fut = b.submit(auto.run)
    t0 = time.time()
    while not fut.done() and time.time() - t0 < timeout:
        if not auto.run_evt.is_set() and on_pause:
            on_pause(auto, b, logs)
        time.sleep(0.2)
    if not fut.done():
        auto.stop(); fut.result(timeout=15)
        pytest.fail("automation did not finish:\n" + "\n".join(logs[-15:]))
    fut.result()
    b.call(b.close)
    return logs, done


def test_full_flow_stops_at_chapter_17_and_never_enters_18(env):
    srv, base = mock_site.serve(start_chapter=15)
    handled = {"exam": 0}

    def on_pause(auto, b, logs):
        # The only expected pause is the graded exam. The "user" answers it, then resumes.
        assert "Answer this assessment yourself" in "\n".join(logs[-3:]) or any("assessment" in l.lower() for l in logs)
        handled["exam"] += 1
        auto.resume()

    logs, done = run_auto(base, base + "/dashboard", on_pause=on_pause)
    srv.shutdown()

    assert done["ok"] is True and done["msg"] == chapter_guard.DONE_MESSAGE
    assert not any("/chapter-18" in h for h in mock_site.HITS), mock_site.HITS
    assert any("/chapter-17/quiz" in h for h in mock_site.HITS)       # did work through chapter 17
    assert handled["exam"] == 1 and env["explain"] == 1               # exam paused once, AI only explained
    assert env["wrong_first"] == 1                                    # rejected once, then retried and accepted
    # the exam page was never answered by the bot: its textarea must not have been touched
    assert not any("Attempt" in l and "Final Exam" in l for l in logs)


def test_chapter_17_js_button_next_is_blocked_at_network_level(env):
    srv, base = mock_site.serve(start_chapter=17, js_last_next=True)
    logs, done = run_auto(base, base + "/dashboard")
    srv.shutdown()
    assert done["ok"] and done["msg"] == chapter_guard.DONE_MESSAGE
    assert not any("/chapter-18" in h for h in mock_site.HITS)


def test_unidentifiable_chapter_pauses_instead_of_continuing(env):
    srv, base = mock_site.serve()
    b = QureoBrowser(); logs = []
    auto = Automation(b, lambda: "k", lambda: "m", logs.append, lambda *a: None, lambda *a: None)
    b.call(b.open, base + "/")          # welcome page: no chapter, no Continue button
    fut = b.submit(auto.run)
    t0 = time.time()
    while auto.run_evt.is_set() and time.time() - t0 < 20:
        time.sleep(0.2)
    assert not auto.run_evt.is_set(), "should have paused"
    assert any("Cannot identify the chapter" in l for l in logs)
    auto.stop(); fut.result(timeout=15); b.call(b.close); srv.shutdown()


def test_login_fills_form_and_detects_captcha():
    srv, base = mock_site.serve()
    b = QureoBrowser()
    b.call(b.open, base + "/login")
    assert b.call(b.try_login, "me@example.com", "secret") == "logged_in"
    assert b.call(lambda: b.page.url).endswith("/dashboard")
    b.call(b.page.goto, base + "/captcha")
    assert b.call(b.try_login, "me@example.com", "secret") == "needs_manual"
    b.call(b.close); srv.shutdown()
