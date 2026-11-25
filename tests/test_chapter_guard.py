import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import chapter_guard as g


def test_reads_clear_chapter():
    r = g.read_chapter("Chapter 12: Loops", "https://x/chapter-12/lesson", "Loops")
    assert r.reliable and r.chapter == 12


def test_no_chapter_is_unreliable():
    r = g.read_chapter("My courses", "https://x/dashboard", "Dashboard")
    assert not r.reliable and r.chapter is None


def test_conflicting_sources_are_unreliable():
    r = g.read_chapter("Chapter 5", "https://x/chapter-6/lesson", "")
    assert not r.reliable


def test_multiple_chapters_in_heading_unreliable():
    assert not g.read_chapter("Chapter 3\nChapter 4", "", "").reliable


def test_may_act_boundaries():
    assert g.may_act_in(g.read_chapter("Chapter 17", "", ""))
    assert not g.may_act_in(g.read_chapter("Chapter 18", "", ""))
    assert not g.may_act_in(g.ChapterReading(None, False, "x"))


def test_forbidden_targets():
    assert g.target_is_forbidden("Chapter 18")
    assert g.target_is_forbidden("Next", "/course/chapter-18/lesson-1")
    assert g.target_is_forbidden("Go to Chapter 25")
    assert not g.target_is_forbidden("Next", "/chapter-17/lesson-9")
    assert not g.target_is_forbidden("Next lesson", "")


def test_progress_fraction():
    assert g.progress_fraction(None) == 0
    assert g.progress_fraction(17, True) == 1
    assert 0 < g.progress_fraction(5) < 1
