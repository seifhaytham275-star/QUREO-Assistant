"""Strict chapter-limit logic. Pure functions, no browser, easy to unit test.

Rule: automation may act only while the chapter number is *reliably* known
and is <= LAST_CHAPTER. Anything ambiguous means PAUSE, never continue.
"""
import re
from dataclasses import dataclass
from typing import Optional

LAST_CHAPTER = 17
DONE_MESSAGE = "Chapter 17 completed. Automation stopped."

# Matches "Chapter 17", "chapter 3:", "Ch. 5", "Chapter 12 - Loops" ...
_CH = re.compile(r"\b(?:chapter|ch\.?)\s*0*(\d{1,3})\b", re.I)


def find_chapter_numbers(text: str):
    return [int(m.group(1)) for m in _CH.finditer(text or "")]


@dataclass
class ChapterReading:
    chapter: Optional[int]      # None when not reliable
    reliable: bool
    reason: str = ""


def read_chapter(heading_text: str, url: str = "", title: str = "") -> ChapterReading:
    """Determine the current chapter from the *current-location* text only
    (breadcrumb/heading), cross-checked against URL and page title.

    Reliable = at least one source names a chapter and no two sources disagree.
    """
    found = []
    for label, src in (("heading", heading_text), ("title", title)):
        nums = set(find_chapter_numbers(src))
        if len(nums) > 1:
            return ChapterReading(None, False, f"{label} names several chapters {sorted(nums)}")
        if nums:
            found.append((label, nums.pop()))
    m = re.search(r"chapter[-_/ ]?0*(\d{1,3})", url or "", re.I)
    if m:
        found.append(("url", int(m.group(1))))
    if not found:
        return ChapterReading(None, False, "no chapter number visible")
    values = {n for _, n in found}
    if len(values) > 1:
        return ChapterReading(None, False, f"sources disagree: {found}")
    return ChapterReading(values.pop(), True)


def may_act_in(reading: ChapterReading) -> bool:
    """True only if it is safe to work on the current page."""
    return reading.reliable and reading.chapter is not None and reading.chapter <= LAST_CHAPTER


def target_is_forbidden(label: str, href: str = "") -> bool:
    """True if a link/button would lead beyond the last chapter."""
    for n in find_chapter_numbers(label):
        if n > LAST_CHAPTER:
            return True
    m = re.search(r"chapter[-_/ ]?0*(\d{1,3})", href or "", re.I)
    return bool(m and int(m.group(1)) > LAST_CHAPTER)


def progress_fraction(chapter: Optional[int], chapter_done: bool = False) -> float:
    if chapter is None:
        return 0.0
    done = chapter if chapter_done else chapter - 1
    return max(0.0, min(1.0, done / LAST_CHAPTER))
