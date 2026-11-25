"""OpenRouter-backed exercise solver.

The model must answer with JSON so the automation can act on it safely.
"""
import json
import re

OPENROUTER_URL = "https://openrouter.ai/api/v1"

MODELS = [
    "openai/gpt-4o-mini",
    "openai/gpt-4o",
    "anthropic/claude-3.5-sonnet",
    "google/gemini-2.0-flash-001",
    "deepseek/deepseek-chat",
]

SYSTEM = (
    "You are a patient tutor helping a student practise on the QUREO course "
    "(JavaScript, HTML, CSS). You get the visible text of ONE exercise page. "
    "Reply with a single JSON object and nothing else, with keys: "
    '"type" (one of "multiple_choice","code","fill_blank","unknown"), '
    '"answer" (for multiple_choice: the exact option text or its letter; '
    'for code: the complete code to put in the editor; '
    'for fill_blank: a JSON list of strings, one per blank, in order), '
    '"explanation" (1-3 short sentences). '
    "Use only what is shown on the page. If the page does not contain enough "
    'information, return type "unknown" and say what is missing. If previous '
    "feedback is provided, read it and fix the specific problem."
)


def _client(api_key: str):
    from openai import OpenAI
    return OpenAI(api_key=api_key, base_url=OPENROUTER_URL, timeout=60)


def parse_reply(text: str) -> dict:
    """Extract the JSON object from a model reply (tolerates code fences)."""
    text = (text or "").strip()
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("Model reply contained no JSON")
    data = json.loads(m.group(0))
    data.setdefault("type", "unknown")
    data.setdefault("answer", "")
    data.setdefault("explanation", "")
    return data


def solve(api_key: str, model: str, page_text: str, feedback: str = "", attempt: int = 1) -> dict:
    user = f"EXERCISE PAGE TEXT:\n{page_text[:12000]}\n"
    if feedback:
        user += f"\nPREVIOUS ATTEMPT {attempt - 1} WAS REJECTED. PLATFORM FEEDBACK:\n{feedback[:3000]}\n"
    resp = _client(api_key).chat.completions.create(
        model=model, temperature=0.1,
        messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
    )
    return parse_reply(resp.choices[0].message.content or "")


def explain(api_key: str, model: str, page_text: str) -> str:
    """Short explanation only (used for graded assessments: no answer is applied)."""
    resp = _client(api_key).chat.completions.create(
        model=model, temperature=0.2,
        messages=[
            {"role": "system", "content": "Briefly explain the concepts behind this question and how to reason about it, for a student who will answer it themselves. Keep it under 150 words."},
            {"role": "user", "content": page_text[:12000]},
        ],
    )
    return resp.choices[0].message.content or ""
