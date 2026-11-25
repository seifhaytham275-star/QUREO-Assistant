"""QUREO Assistant — desktop app (Tkinter).

All Playwright work happens on the browser's own worker thread; the GUI only
talks to it through submit()/call() and receives updates through a queue.
"""
import queue
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText

import ai_solver
import chapter_guard
import credentials
from automation import Automation
from browser_helper import QureoBrowser, START_URL

APP_TITLE = "QUREO Assistant · Automated learning through Chapter 17"


class App:
    def __init__(self, root):
        self.root = root
        root.title(APP_TITLE)
        root.geometry("980x860")
        self.q = queue.Queue()
        self.browser = QureoBrowser()
        self.auto = None
        self.running = False

        self.var_url = tk.StringVar(value=START_URL)
        self.var_user = tk.StringVar()
        self.var_pass = tk.StringVar()
        self.var_show = tk.BooleanVar(value=False)
        self.var_remember = tk.BooleanVar(value=False)
        self.var_key = tk.StringVar()
        self.var_model = tk.StringVar(value=ai_solver.MODELS[0])
        self.var_auto = tk.BooleanVar(value=True)
        self.var_chapter = tk.StringVar(value="Chapter: –")
        self.var_lesson = tk.StringVar(value="Lesson: –")
        self.var_status = tk.StringVar(value="Idle")

        self._build()
        self._load_saved()
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(100, self._drain)

    # ---------------------------------------------------------------- UI
    def _build(self):
        r = self.root
        ttk.Label(r, text="QUREO Assistant", font=("Segoe UI", 20, "bold")).pack(pady=(10, 0))
        ttk.Label(r, text="Signs in with your own account and works through practice exercises up to Chapter 17. "
                          "Graded tests are never answered for you.", wraplength=920).pack(pady=(0, 6))

        login = ttk.LabelFrame(r, text="1 · QUREO login")
        login.pack(fill="x", padx=12, pady=4)
        ttk.Label(login, text="Course link").grid(row=0, column=0, sticky="w", padx=6, pady=3)
        ttk.Entry(login, textvariable=self.var_url, width=70).grid(row=0, column=1, columnspan=2, sticky="w", padx=6)
        ttk.Label(login, text="Email / username").grid(row=1, column=0, sticky="w", padx=6, pady=3)
        ttk.Entry(login, textvariable=self.var_user, width=40).grid(row=1, column=1, sticky="w", padx=6)
        ttk.Label(login, text="Password").grid(row=2, column=0, sticky="w", padx=6, pady=3)
        self.ent_pass = ttk.Entry(login, textvariable=self.var_pass, show="•", width=40)
        self.ent_pass.grid(row=2, column=1, sticky="w", padx=6)
        ttk.Checkbutton(login, text="Show", variable=self.var_show, command=self._toggle_show).grid(row=2, column=2, sticky="w")
        ttk.Checkbutton(login, text="Remember login (Windows Credential Manager)", variable=self.var_remember).grid(row=3, column=1, sticky="w", padx=6)
        bar = ttk.Frame(login); bar.grid(row=4, column=0, columnspan=3, sticky="w", padx=6, pady=4)
        ttk.Button(bar, text="Open QUREO", command=self.open_qureo).pack(side="left", padx=3)
        ttk.Button(bar, text="Login", command=self.login).pack(side="left", padx=3)
        ttk.Button(bar, text="Forget saved login", command=self.forget).pack(side="left", padx=3)

        ai = ttk.LabelFrame(r, text="2 · OpenRouter")
        ai.pack(fill="x", padx=12, pady=4)
        ttk.Label(ai, text="API key").grid(row=0, column=0, sticky="w", padx=6, pady=3)
        ttk.Entry(ai, textvariable=self.var_key, show="•", width=55).grid(row=0, column=1, sticky="w", padx=6)
        ttk.Label(ai, text="Model").grid(row=1, column=0, sticky="w", padx=6, pady=3)
        ttk.Combobox(ai, textvariable=self.var_model, values=ai_solver.MODELS, width=52).grid(row=1, column=1, sticky="w", padx=6)

        prog = ttk.LabelFrame(r, text="3 · Progress")
        prog.pack(fill="x", padx=12, pady=4)
        ttk.Label(prog, textvariable=self.var_chapter, font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=6)
        ttk.Label(prog, textvariable=self.var_lesson, wraplength=900).pack(anchor="w", padx=6)
        self.bar = ttk.Progressbar(prog, maximum=chapter_guard.LAST_CHAPTER, length=600)
        self.bar.pack(anchor="w", padx=6, pady=4)
        ttk.Label(prog, textvariable=self.var_status).pack(anchor="w", padx=6)

        ctl = ttk.Frame(r); ctl.pack(fill="x", padx=12, pady=6)
        ttk.Checkbutton(ctl, text="Auto Practice", variable=self.var_auto).pack(side="left", padx=6)
        self.btn_start = ttk.Button(ctl, text="▶ Start", command=self.start); self.btn_start.pack(side="left", padx=3)
        self.btn_pause = ttk.Button(ctl, text="⏸ Pause", command=self.pause_resume, state="disabled"); self.btn_pause.pack(side="left", padx=3)
        self.btn_stop = ttk.Button(ctl, text="⏹ Stop", command=self.stop, state="disabled"); self.btn_stop.pack(side="left", padx=3)

        ttk.Label(r, text="Activity log").pack(anchor="w", padx=12)
        self.log_box = ScrolledText(r, height=16, wrap="word", state="disabled")
        self.log_box.pack(fill="both", expand=True, padx=12, pady=(0, 10))

    def _toggle_show(self):
        self.ent_pass.config(show="" if self.var_show.get() else "•")

    # ------------------------------------------------- thread-safe plumbing
    def log(self, msg):
        self.q.put(("log", msg))

    def _drain(self):
        try:
            while True:
                kind, *a = self.q.get_nowait()
                if kind == "log":
                    if a[0].startswith("⏸ Paused"):
                        self.btn_pause.config(text="▶ Resume"); self.var_status.set("Paused — action needed")
                    elif a[0].startswith("▶ Resumed"):
                        self.btn_pause.config(text="⏸ Pause"); self.var_status.set("Running")
                    self.log_box.config(state="normal")
                    self.log_box.insert("end", a[0] + "\n"); self.log_box.see("end")
                    self.log_box.config(state="disabled")
                elif kind == "progress":
                    ch, snap = a
                    self.var_chapter.set(f"Chapter: {ch if ch is not None else '?'} of {chapter_guard.LAST_CHAPTER}")
                    self.var_lesson.set("Lesson: " + (snap.get("title") or snap.get("url", ""))[:120])
                    self.bar["value"] = (ch - 1) if ch else 0
                elif kind == "done":
                    msg, completed = a
                    self.running = False
                    self.var_status.set(msg)
                    if completed:
                        self.bar["value"] = chapter_guard.LAST_CHAPTER
                        self.var_chapter.set(f"Chapter: {chapter_guard.LAST_CHAPTER} of {chapter_guard.LAST_CHAPTER} ✔")
                        messagebox.showinfo("Done", chapter_guard.DONE_MESSAGE)
                    self._buttons()
                elif kind == "error":
                    messagebox.showerror("Error", a[0])
        except queue.Empty:
            pass
        self.root.after(100, self._drain)

    def _buttons(self):
        self.btn_start.config(state="disabled" if self.running else "normal")
        self.btn_pause.config(state="normal" if self.running else "disabled", text="⏸ Pause")
        self.btn_stop.config(state="normal" if self.running else "disabled")

    # ---------------------------------------------------------- credentials
    def _load_saved(self):
        u, p = credentials.load_qureo()
        if u:
            self.var_user.set(u); self.var_pass.set(p or ""); self.var_remember.set(True)
        k = credentials.load_openrouter_key()
        if k:
            self.var_key.set(k)

    def forget(self):
        credentials.clear_qureo()
        self.var_user.set(""); self.var_pass.set(""); self.var_remember.set(False)
        self.log("Saved login removed from Windows Credential Manager.")

    # -------------------------------------------------------------- actions
    def _bg(self, fn, on_error="Browser error"):
        def run():
            try:
                fn()
            except Exception as e:
                self.q.put(("error", f"{on_error}: {e}"))
        self.browser.submit(run)

    def open_qureo(self):
        url = self.var_url.get().strip() or START_URL
        self.log(f"Opening {url} in Microsoft Edge…")
        self._bg(lambda: self.browser.open(url))

    def login(self):
        user, pw = self.var_user.get().strip(), self.var_pass.get()
        if not user or not pw:
            messagebox.showwarning("Login", "Enter your QUREO email/username and password."); return
        if self.var_remember.get():
            try:
                credentials.save_qureo(user, pw)
            except Exception:
                messagebox.showwarning("Credential storage", "Could not save to the secure store; login will not be remembered.")
        url = self.var_url.get().strip() or START_URL
        def work():
            self.browser.open(url)
            res = self.browser.try_login(user, pw)
            if res == "logged_in":
                self.log("✔ Signed in.")
            elif res == "needs_manual":
                self.log("Please finish signing in (CAPTCHA / verification / code) in the Edge window.")
            else:
                self.log("No login form found. Sign in manually in the Edge window.")
        self._bg(work)

    def start(self):
        if not self.var_key.get().strip():
            messagebox.showwarning("OpenRouter", "Enter your OpenRouter API key."); return
        if self.var_key.get().strip() and self.var_remember.get():
            try: credentials.save_openrouter_key(self.var_key.get().strip())
            except Exception: pass
        self.auto = Automation(
            self.browser,
            get_key=lambda: self.var_key.get().strip(),
            get_model=lambda: self.var_model.get().strip() or ai_solver.MODELS[0],
            log=self.log,
            on_progress=lambda ch, snap: self.q.put(("progress", ch, snap)),
            on_done=lambda msg, ok: self.q.put(("done", msg, ok)),
            auto_practice=lambda: self.var_auto.get(),
            login=lambda: (self.var_user.get().strip(), self.var_pass.get()),
            start_url=lambda: self.var_url.get().strip() or START_URL,
        )
        self.running = True
        self.var_status.set("Running")
        self._buttons()
        self.log("▶ Auto Practice started (stops after Chapter 17).")
        auto = self.auto
        self._bg(auto.run, "Automation error")

    def pause_resume(self):
        if not self.auto:
            return
        if self.auto.run_evt.is_set():
            self.auto.pause("Paused by user."); self.btn_pause.config(text="▶ Resume"); self.var_status.set("Paused")
        else:
            self.auto.resume(); self.btn_pause.config(text="⏸ Pause"); self.var_status.set("Running")

    def stop(self):
        if self.auto:
            self.auto.stop()
            self.log("Stopping…")

    def close(self):
        if self.auto:
            self.auto.stop()
        try:
            self.browser.submit(self.browser.close).result(timeout=10)
        except Exception:
            pass
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
