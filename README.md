# QUREO Assistant

Windows desktop app (Python · Tkinter · Playwright · Microsoft Edge) that signs in to **your own** QUREO account and works through practice exercises up to **Chapter 17**, using an OpenRouter model to solve them.

## What it does
- **Login panel** – email/username, password (show/hide), *Remember login* (stored in **Windows Credential Manager** via `keyring`; never in a file, never logged). If QUREO shows a CAPTCHA, email verification or a code, the app **pauses** and waits for you.
- **Course progress** – detects the current chapter/lesson from the page, resumes from your real progress (uses the course's own *Continue/Resume* control), shows a 17-chapter progress bar.
- **Auto Practice** – reads the exercise → asks the AI → fills the answer field / code editor / choice / blanks → presses *Check* → reads the feedback → retries (max 3, using the platform's feedback) → moves on **only after it is accepted**. Pause / Resume / Stop at any time.
- **Chapter 17 limit** – the chapter number must be read reliably from the visible heading, URL and title (they must agree), otherwise the app **pauses**. It stops with `Chapter 17 completed. Automation stopped.` and refuses to follow any link/button that points to Chapter 18+; navigation to URLs naming Chapter 18+ is also blocked at the network level, and a post-click check backs out if a Chapter 18 page ever loads.
- **Assessment protection** – pages that look like graded tests/exams (e.g. *exam*, *final assessment*, *graded quiz*, time-limited/one-attempt wording) are **never answered**. The app shows an AI *explanation* in the log, pauses, and lets you answer yourself.

No hidden answer databases, no bypassing of platform restrictions.

## Install
Download **QUREO-Assistant-Setup.exe** from the [Releases](../../releases) page, run it, and make sure Microsoft Edge is installed.

## Use
1. Check the **Course link** box (default https://me-tp.qureo.education/course/javascript_en; paste your own if different), then *Open QUREO* or *Login*. *Start* also opens the browser and signs in by itself.
2. Enter your OpenRouter API key and choose a model.
3. Press **Start**. Watch the Activity log; use **Pause**/**Stop** whenever you like.

## Run from source
```
pip install -r requirements.txt
python main.py
```
Tests (use Chromium, a local mock course site and a fake AI — no network, no QUREO account):
```
pip install -r requirements-dev.txt
QUREO_BROWSER_CHANNEL=chromium pytest tests -q        # PowerShell: $env:QUREO_BROWSER_CHANNEL="chromium"
```

## Files
| File | Role |
|---|---|
| `main.py` | Tkinter GUI |
| `automation.py` | Auto Practice loop, pause/stop, retries, assessment protection |
| `chapter_guard.py` | Chapter detection and the strict Chapter 17 limit |
| `browser_helper.py` | Edge/Playwright: login, reading, answering, navigation |
| `ai_solver.py` | OpenRouter prompts and reply parsing |
| `credentials.py` | Windows Credential Manager storage |

## Known limitations (please read)
- QUREO's page markup is not public, so element detection is **heuristic** (button names like *Check/Submit/Run/Next*, common editors: Monaco, CodeMirror, Ace, textarea). It has been tested against a local mock course, **not** against the live QUREO site. If something isn't detected, the app pauses rather than guessing; adjust the selectors at the top of `browser_helper.py`.
- Using automation on a learning platform may be restricted by QUREO's terms of use, and completing exercises automatically means you may not learn the material. You are responsible for how you use it.
- AI answers can be wrong; the app relies on QUREO's own feedback to decide whether an answer was accepted.
