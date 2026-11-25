"""Tiny local mock of a course site, used only for testing the automation.

Flow per chapter N:  lesson -> exercise (code) -> quiz (multiple choice) -> next chapter.
Chapter 16 also has a graded final exam before Chapter 17.
Chapter 17's last Next leads to /chapter-18/lesson (must never be entered).
"""
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

HITS = []  # every path requested (so tests can assert Chapter 18 was never fetched)


def page(n, title, body, nxt, active_chapter=None, js_next=False):
    side = "".join(
        f'<li class="{"active" if i == (active_chapter or n) else ""}"><a href="/chapter-{i}/lesson">Chapter {i}</a></li>'
        for i in range(1, 20))
    nav = (f'<button id="nx" onclick="location.href=\'{nxt}\'">Next</button>' if js_next
           else f'<a class="btn" href="{nxt}">Next</a>')
    return f"""<!doctype html><html><head><title>{title}</title></head><body>
<ul class="sidebar">{side}</ul>
<h1>Chapter {n}: {title}</h1>{body}<div class="feedback" style="display:none"></div>{nav}</body></html>"""


CODE = """<p>Write code that prints hi.</p><textarea class="code-editor" rows="4" cols="40"></textarea>
<button onclick="var v=document.querySelector('textarea').value;var f=document.querySelector('.feedback');
f.style.display='block';f.textContent=v.indexOf('console.log')>=0?'Correct! Well done.':'Incorrect, try again. Use console.log.'">Check</button>"""

MC = """<p>Which keyword declares a constant?</p>
<label><input type="radio" name="q" value="a"> var</label><br>
<label><input type="radio" name="q" value="b"> const</label><br>
<label><input type="radio" name="q" value="c"> print</label><br>
<button onclick="var r=document.querySelector('input:checked');var f=document.querySelector('.feedback');
f.style.display='block';f.textContent=(r&&r.value=='b')?'Correct! Nice work.':'Incorrect, try again.'">Check</button>"""

EXAM = "<p>Final Exam question: What does DOM stand for?</p><textarea rows=3></textarea>"

LOGIN = """<!doctype html><html><head><title>Login</title></head><body><h1>Sign in</h1>
<form onsubmit="location.href='/dashboard';return false"><input type="email" name="email">
<input type="password" name="password"><button>Sign in</button></form></body></html>"""

CAPTCHA = """<!doctype html><html><body><h1>Sign in</h1><div class="g-recaptcha">I'm not a robot</div>
<input type="email" name="email"><input type="password"></body></html>"""

DASH = """<!doctype html><html><head><title>Dashboard</title></head><body><h1>My courses</h1>
<a href="/chapter-{c}/lesson">Continue</a></body></html>"""


def make_handler(start_chapter, js_last_next=False):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            p = self.path.split("?")[0]
            HITS.append(p)
            parts = [x for x in p.split("/") if x]
            html = None
            if p == "/":
                html = '<html><body><h1>Welcome</h1><a href="/login">Log in</a></body></html>'
            elif p == "/login":
                html = LOGIN
            elif p == "/captcha":
                html = CAPTCHA
            elif p == "/dashboard":
                html = DASH.replace("{c}", str(start_chapter))
            elif len(parts) == 2 and parts[0].startswith("chapter-"):
                n = int(parts[0].split("-")[1])
                step = parts[1]
                if step == "lesson":
                    html = page(n, "Intro", "<p>Lesson text about variables.</p>", f"/chapter-{n}/exercise")
                elif step == "exercise":
                    html = page(n, "Practice", CODE, f"/chapter-{n}/quiz")
                elif step == "quiz":
                    if n == 16:
                        nxt = "/chapter-16/exam"
                    else:
                        nxt = f"/chapter-{n + 1}/lesson"
                    html = page(n, "Quiz practice", MC, nxt, js_next=(js_last_next and n == 17))
                elif step == "exam":
                    html = page(16, "Final Exam", EXAM, "/chapter-17/lesson")
            if html is None:
                self.send_response(404); self.end_headers(); return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode())
    return H


def serve(start_chapter=15, js_last_next=False):
    HITS.clear()
    srv = HTTPServer(("127.0.0.1", 0), make_handler(start_chapter, js_last_next))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}"
