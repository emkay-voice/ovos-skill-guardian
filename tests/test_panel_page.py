"""Guardian's page in ovos-control-panel, described in controlpanel.json: the
file, its strings in every language the skill speaks, and the skill's answers
to the page over the bus."""
import json
import re
import time
from pathlib import Path

import pytest

import test_skill
from test_skill import entry, phal, skill, write  # noqa: F401 - skill is a fixture

pkg = test_skill.pkg

ROOT = Path(__file__).resolve().parents[1]
TEXT = (ROOT / "controlpanel.json").read_text(encoding="utf-8")
PAGE = json.loads(TEXT)


def test_the_page_names_files_that_exist_and_its_own_messages():
    assert PAGE["controlpanel"] == 1 and PAGE["id"] == "guardian" and PAGE["path"] == "/privacy"
    assert (ROOT / PAGE["icon"]).is_file()
    sent = re.findall(r'"(?:query|send)": "([^"]+)"', TEXT)
    assert sent and all(m.startswith(PAGE["bus"]) for m in sent)
    assert set(sent) == {pkg.GUARDIAN_STATUS, pkg.GUARDIAN_NETWORK, pkg.GUARDIAN_LOCAL_ONLY}
    periods = next(b for b in PAGE["blocks"] if b["type"] == "choice")["options"]
    assert [o["value"] for o in periods] == list(pkg.PERIODS)


def test_the_page_speaks_every_language_the_skill_does():
    files = {p.parent.name: json.loads(p.read_text(encoding="utf-8"))
             for p in (ROOT / "locale").glob("*/controlpanel.json")}
    assert set(files) == {p.name for p in (ROOT / "locale").iterdir() if p.is_dir()}
    keys = set(files["en-US"])
    for lang, table in files.items():
        assert set(table) == keys, lang
        assert all(text.strip() for text in table.values()), lang
        assert "{total}" in table["guardian.net.sum"] and "{service_count}" in table["guardian.net.sum"], lang
        assert "{refused}" in table["guardian.net.sumRefused"], lang
    used = set(re.findall(r'"(guardian\.[\w.]+)"', TEXT))
    words = {f"guardian.where.{w}" for w in ("device", "browser", "server", "none")} \
        | {f"guardian.local.{w}" for w in ("on", "off", "unknown")}
    assert used | words == keys, "every string is used, and every one used is there"


def test_the_panel_reads_it():
    described = pytest.importorskip("ovos_webui.described")
    page, refs = described.check(PAGE, "ovos-skill-guardian")
    assert [b["type"] for b in page["blocks"]] == ["text", "status", "choice", "status", "list", "list", "text"]
    assert not refs["b1.a0"]["privileged"], "local only is the device's own switch, as by voice"


def answer(skill, msg_type, **data):
    return test_skill.answer(skill, msg_type, **data)


def test_what_went_out_by_period(skill):  # noqa: F811
    write(skill, [entry("wikipedia", "da.wikipedia.org", "ovos-skill-wikipedia")]
          + [dict(entry("stt", "stt.example", "ovos-stt-plugin-server"), blocked=True)]
          + [entry("radio", "radio.example", "ovos-skill-radio", ago=3 * 86400)])
    today = answer(skill, pkg.GUARDIAN_NETWORK, period="today")
    assert [s["kind"] for s in today["services"]] == ["wikipedia", "stt"]
    assert (today["total"], today["refused"], today["service_count"]) == (2, 1, 2)
    assert today["services"][0]["key"] == "wikipedia:da.wikipedia.org" and today["services"][0]["last_s"] > 0
    first = today["entries"][0]
    assert first["blocked"] and first["id"] == "0" and abs(first["when"] - time.time()) < 3600
    week = answer(skill, pkg.GUARDIAN_NETWORK, period="week")
    assert {s["kind"] for s in week["services"]} == {"wikipedia", "stt", "radio"}
    assert answer(skill, pkg.GUARDIAN_NETWORK, period="ever")["services"] == today["services"], "today"


def test_yesterday_stops_at_midnight():
    since, until = pkg.period_bounds("yesterday")
    assert until == pkg.start_of_today() and 22 * 3600 < until - since < 26 * 3600


def test_the_status_and_the_switch(skill, monkeypatch):  # noqa: F811
    monkeypatch.setattr(pkg, "ANSWER_TIMEOUT", 0.2)
    skill.config_core["stt"] = {"module": "ovos-stt-plugin-server"}
    status = answer(skill, pkg.GUARDIAN_STATUS)
    assert status["local"] == "unknown" and status["cannot_switch"] and not status["can_go_offline"]
    assert status["hears"] == "server" and status["hears_server"] and not status["hears_browser"]
    assert answer(skill, pkg.GUARDIAN_LOCAL_ONLY, enabled=True) == {"error": "guardian.local.cannot"}
    state = phal(skill, False)
    assert answer(skill, pkg.GUARDIAN_STATUS)["can_go_offline"]
    assert answer(skill, pkg.GUARDIAN_LOCAL_ONLY, enabled=True) == {"enabled": True}
    assert state["enabled"] is True
    status = answer(skill, pkg.GUARDIAN_STATUS)
    assert status["local"] == "on" and status["can_go_online"] and not status["can_go_offline"]
