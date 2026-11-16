"""Guardian reads the network log and says what went out, in English and Danish."""
import importlib.util
import json
import sys
import time
from pathlib import Path

import pytest
from ovos_bus_client.message import Message
from ovos_utils.fakebus import FakeBus

ROOT = Path(__file__).parent.parent
_spec = importlib.util.spec_from_file_location("ovos_skill_guardian", ROOT / "__init__.py",
                                               submodule_search_locations=[str(ROOT)])
pkg = importlib.util.module_from_spec(_spec)
sys.modules["ovos_skill_guardian"] = pkg
_spec.loader.exec_module(pkg)


def entry(kind, host, who, ago=60, service=None):
    return {"t": int((time.time() - ago) * 1000), "host": host, "method": "GET", "status": 200,
            "bytes": 100, "who": who, "kind": kind, "service": service or host}


@pytest.fixture
def skill(tmp_path):
    bus = FakeBus()
    spoken = []
    bus.on("speak", lambda m: spoken.append(Message.deserialize(m) if isinstance(m, str) else m))
    s = pkg.GuardianSkill(bus=bus, skill_id="ovos-skill-guardian.emkay-voice")
    s.settings["log_path"] = str(tmp_path / "network.jsonl")
    s.spoken = spoken
    yield s
    s.shutdown()


def write(skill, entries):
    Path(skill.settings["log_path"]).write_text("".join(json.dumps(e) + "\n" for e in entries))


def said(skill):
    return skill.spoken[-1].data["utterance"]


def test_no_log(skill):
    skill.handle_sent_today(Message("x"))
    assert "log" in said(skill)


def test_nothing_today(skill):
    write(skill, [entry("wikipedia", "en.wikipedia.org", "ovos-skill-wikipedia", ago=3 * 86400),
                  entry("self", "app.emkay.ai", "emkay")])
    skill.handle_sent_today(Message("x"))
    assert "anything" in said(skill)


def test_sent_today(skill):
    write(skill, [entry("wikipedia", "da.wikipedia.org", "ovos-skill-wikipedia")] * 3
          + [entry("tts", "tts.openvoiceos.pt", "ovos-tts-plugin-server")]
          + [entry("other", "blog.openvoiceos.org", "ovos-skill-ovosblog", service="blog.openvoiceos.org")]
          + [entry("self", "app.emkay.ai", "emkay")] * 20)
    skill.handle_sent_today(Message("x"))
    text = said(skill)
    assert "3 services" in text
    assert "Wikipedia 3 times" in text and "the voice once" in text
    assert "blog.openvoiceos.org" in text and "app.emkay.ai" not in text


def test_who_hears_me_remote(skill):
    skill.config_core["stt"] = {"module": "ovos-stt-plugin-server"}
    write(skill, [entry("stt", "stt.openvoiceos.pt", "ovos-stt-plugin-server")])
    skill.handle_who_hears_me(Message("x"))
    assert "stt.openvoiceos.pt" in said(skill)


def test_who_hears_me_local(skill):
    skill.config_core["stt"] = {"module": "ovos-stt-plugin-whisper-browser"}
    skill.handle_who_hears_me(Message("x"))
    assert "on the device" in said(skill)


LANGS = ["en-US", "da-DK", "de-DE", "nl-NL", "fr-FR", "es-ES", "it-IT",
         "pt-BR", "pt-PT", "ca-ES", "gl-ES", "eu-ES"]


@pytest.mark.parametrize("lang", LANGS)
def test_every_dialog_exists(lang):
    loc = ROOT / "locale" / lang
    code = (ROOT / "__init__.py").read_text()
    for intent in loc.glob("*.intent"):
        assert f'"{intent.name}"' in code, intent.name
    names = ["sent_today", "sent_today_more", "times", "times_one", "and", "sent_nothing", "no_log",
             "stt_local", "stt_browser", "stt_remote_seen", "stt_remote",
             *(f"kind_{k}" for k in pkg.KINDS)]
    for d in names:
        assert (loc / f"{d}.dialog").read_text(encoding="utf-8").strip(), d


# -- local only --------------------------------------------------------------

def phal(skill, enabled):
    """A PHAL plugin that answers ovos.local_only[.status]."""
    state = {"enabled": enabled}

    def switch(m):
        m = Message.deserialize(m) if isinstance(m, str) else m
        state["enabled"] = m.data["enabled"]
        skill.bus.emit(m.response({**state, "stt": "x", "tts": "y"}))

    def ask(m):
        m = Message.deserialize(m) if isinstance(m, str) else m
        skill.bus.emit(m.response({**state, "stt": "x", "tts": "y"}))
    skill.bus.on("ovos.local_only", switch)
    skill.bus.on("ovos.local_only.status", ask)
    return state


def last(skill):
    return skill.spoken[-1].data["meta"]["dialog"]


def test_go_offline_and_online(skill):
    state = phal(skill, False)
    skill.handle_go_offline(Message("x"))
    assert state["enabled"] and last(skill) == "offline_on"
    skill.handle_are_you_online(Message("x"))
    assert last(skill) == "status_local_only"
    skill.handle_go_online(Message("x"))
    assert not state["enabled"] and last(skill) == "offline_off"
    skill.handle_are_you_online(Message("x"))
    assert last(skill) == "status_online"


def test_no_phal(skill, monkeypatch):
    monkeypatch.setattr(pkg, "ANSWER_TIMEOUT", 0.2)
    skill.handle_go_offline(Message("x"))
    assert last(skill) == "no_local_only"
