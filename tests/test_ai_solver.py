import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest
import ai_solver


def test_parse_plain_json():
    d = ai_solver.parse_reply('{"type":"code","answer":"let x=1;","explanation":"e"}')
    assert d["type"] == "code" and d["answer"] == "let x=1;"


def test_parse_fenced_json_and_defaults():
    d = ai_solver.parse_reply("```json\n{\"type\":\"fill_blank\",\"answer\":[\"a\",\"b\"]}\n```")
    assert d["answer"] == ["a", "b"] and d["explanation"] == ""


def test_parse_rejects_non_json():
    with pytest.raises(ValueError):
        ai_solver.parse_reply("sorry, I cannot")
