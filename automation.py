"""Auto Practice engine. Runs on the Playwright worker thread.

Safety rules (all enforced here, not left to the AI):
  * chapter must be reliably identified, otherwise PAUSE
  * never act in, or navigate into, a chapter > 17
  * graded tests / exams: PAUSE, show explanation, never fill or submit
  * CAPTCHA / email verification: PAUSE for the user
  * advance only after the current exercise was accepted
"""
import threading
import time

import ai_solver
import chapter_guard

MAX_STEPS = 3000


class Automation:
    def __init__(self, browser, get_key, get_model, log, on_progress, on_done,
                 max_retries=3, auto_practice=lambda: True, login=None, start_url=None):
        self.b = browser
        self.get_key, self.get_model = get_key, get_model
        self.log, self.on_progress, self.on_done = log, on_progress, on_done
        self.max_retries = max_retries
        self.auto_practice = auto_practice
        self.start_url = start_url
        self.login = login          # optional callable -> (username, password) or None
        self.stop_evt = threading.Event()
        self.run_evt = threading.Event()   # set = running, clear = paused
        self.run_evt.set()
        self.finished = False

    # ---- controls -------------------------------------------------------
    def pause(self, why=""):
        if why:
            self.log(f"⏸ Paused: {why}")
        self.run_evt.clear()

    def resume(self):
        self.log("▶ Resumed")
        self.run_evt.set()

    def stop(self):
        self.stop_evt.set()
        self.run_evt.set()

    def _wait_if_paused(self):
        while not self.run_evt.is_set() and not self.stop_evt.is_set():
            time.sleep(0.3)
        return not self.stop_evt.is_set()

    def _finish(self, msg, done=False):
        self.finished = True
        self.log(msg)
        self.on_done(msg, done)

    # ---- main loop ------------------------------------------------------
    def _ensure_browser(self):
        """Open Edge on the course page if it is not open yet, and sign in if we have credentials."""
        if self.b.alive():
            return
        url = self.start_url() if self.start_url else None
        self.log(f"Opening Microsoft Edge on {url or 'the default course page'}…")
        self.b.open(url) if url else self.b.open()
        creds = self.login() if self.login else None
        if creds and creds[0] and creds[1]:
            res = self.b.try_login(*creds)
            if res == "logged_in":
                self.log("✔ Signed in.")
            else:
                self.pause("Please sign in / finish verification in the Edge window, then press Resume.")

    def run(self):
        try:
            self._ensure_browser()
        except Exception as e:
            self.log(f"⚠ Could not start the browser: {str(e)[:200]}")
            return self._finish("Browser could not be started.")
        state = {"last_sig": None, "same": 0, "resume_tries": 0}
        steps = 0
        while steps < MAX_STEPS:
            steps += 1
            try:
                if self._step(state) == "end":
                    return
            except Exception as e:  # never crash silently
                self.log(f"⚠ Error: {type(e).__name__}: {str(e)[:200]}")
                if self.stop_evt.is_set():
                    return self._finish("⏹ Stopped by user.")
                self.pause("An error occurred. Check the browser, then Resume or Stop.")
        self.pause("Step limit reached for safety.")

    def _step(self, st):
        """One pass of the loop. Returns 'end' when the run is over."""
        if not self._wait_if_paused():
            self._finish("⏹ Stopped by user.")
            return "end"
        if not self.b.alive():
            self._finish("Browser was closed. Automation stopped.")
            return "end"

        if self.b.needs_manual_auth():
            self.pause("CAPTCHA / verification detected. Complete it in the browser, then press Resume.")
            return
        snap = self.b.snapshot()
        reading = self.b.chapter(snap)
        self.on_progress(reading.chapter, snap)

        if reading.reliable and reading.chapter > chapter_guard.LAST_CHAPTER:
            self.b.go_back()
            self._finish(chapter_guard.done_message(), True)
            return "end"

        kind = self.b.classify(snap)

        if not chapter_guard.may_act_in(reading):
            # Home/dashboard? Let the platform resume us, a couple of times at most.
            if kind == "lesson" and st["resume_tries"] < 3 and self.b.resume_course():
                st["resume_tries"] += 1
                self.log("Pressed the course's own Continue/Resume control.")
                return
            self.pause(f"Cannot identify the chapter reliably ({reading.reason}). "
                       "Open a lesson/exercise in the browser and press Resume.")
            st["resume_tries"] = 0
            return
        st["resume_tries"] = 0

        if snap["sig"] == st["last_sig"]:
            st["same"] += 1
        else:
            st["last_sig"], st["same"] = snap["sig"], 0
        if st["same"] >= 3:
            self.pause("The page is not changing (stuck). Please check the browser.")
            st["same"] = 0
            return

        self.log(f"Chapter {reading.chapter} · {kind} · {snap['title'][:60]}")

        if kind == "assessment":
            self._assessment(snap)           # blocks until the user resumes
            if self.stop_evt.is_set():
                self._finish("⏹ Stopped by user.")
                return "end"
        elif kind == "exercise":
            if not self.auto_practice():
                self.pause("Auto Practice is off — exercise left for you.")
                return
            if not self._practice(snap):
                return
        return "end" if not self._advance(reading) else None

    # ---- pieces ---------------------------------------------------------
    def _assessment(self, snap):
        self.log("🛑 Graded test/exam detected — I will not answer it.")
        key = self.get_key()
        if key:
            try:
                self.log("Explanation (for your own reasoning):\n" +
                         ai_solver.explain(key, self.get_model(), snap["text"]))
            except Exception as e:
                self.log(f"(Could not get explanation: {str(e)[:120]})")
        self.pause("Answer this assessment yourself in the browser, then press Resume.")

    def _practice(self, snap):
        """True when the exercise was accepted (or user resolved it)."""
        key = self.get_key()
        if not key:
            self.pause("Enter your OpenRouter API key first.")
            return False
        feedback = ""
        for attempt in range(1, self.max_retries + 1):
            if self.stop_evt.is_set():
                return False
            try:
                sol = ai_solver.solve(key, self.get_model(), snap["text"], feedback, attempt)
            except Exception as e:
                self.log(f"AI error: {str(e)[:150]}")
                time.sleep(2)
                continue
            self.log(f"Attempt {attempt}: {sol.get('type')} — {sol.get('explanation', '')[:200]}")
            if sol.get("type") == "unknown":
                self.pause("The AI could not understand this exercise. Please do it manually.")
                return False
            if not self.b.apply_answer(sol):
                feedback = "Could not enter the answer into the page; the format may be wrong."
                continue
            if not self.b.click_check():
                self.log("No Check/Submit button found; treating as lesson step.")
                return True
            status, fb = self.b.read_feedback()
            self.log(f"Result: {status}" + (f" — {fb[:150]}" if fb else ""))
            if status == "accepted":
                return True
            if status == "unknown":
                self.pause("I can't tell whether the answer was accepted. Please check, then Resume.")
                return False
            feedback = fb
            snap = self.b.snapshot()
        self.pause(f"Not accepted after {self.max_retries} attempts. Please help in the browser, then Resume.")
        return False

    def _advance(self, reading):
        """Move on. Returns False if the run is over."""
        tgt = self.b.next_target()
        at_last = reading.chapter == chapter_guard.LAST_CHAPTER
        if tgt is None and at_last:
            self.b.settle(2000)              # page may still be loading: look once more
            tgt = self.b.next_target()
        if tgt is None:
            if at_last:
                self._finish(chapter_guard.done_message(), True)
                return False
            self.pause("No Next/Continue button found. Navigate manually, then Resume.")
            return True
        _, label, href = tgt
        if chapter_guard.target_is_forbidden(label, href):
            self._finish(chapter_guard.done_message(), True)
            return False
        before = self.b.snapshot()
        self.b.click_next()
        after = self.b.snapshot()
        r2 = self.b.chapter(after)
        if r2.reliable and r2.chapter > chapter_guard.LAST_CHAPTER:
            self.b.go_back()                      # undo immediately, do nothing in Chapter 18
            self._finish(chapter_guard.done_message(), True)
            return False
        if at_last and (after["sig"] == before["sig"] or after["url"].startswith("chrome-error:")):
            # Next led nowhere inside Chapter 17 (or its navigation was blocked): Chapter 17 is done.
            if after["url"].startswith("chrome-error:"):
                self.b.go_back()
            self._finish(chapter_guard.done_message(), True)
            return False
        return True
