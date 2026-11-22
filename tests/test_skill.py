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
             "stt_local", "stt_browser", "stt_remote_seen", "stt_remote", "retry_online", "staying_offline", "offline_again",
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


def test_blocked_requests_were_not_sent(skill):
    """Requests refused in local only ("blocked") never left: not counted."""
    blocked = entry("wikipedia", "da.wikipedia.org", "ovos-skill-wikipedia", service="Wikipedia")
    blocked["blocked"], blocked["status"] = True, 0
    write(skill, [blocked])
    skill.handle_sent_today(Message("x"))
    assert skill.spoken[-1].data["meta"]["dialog"] == "sent_nothing"


# -- what just happened --------------------------------------------------------

def turn(skill, said, skill_id="", intent="", answer="", session="s1"):
    """One turn on the bus, as OVOS sends it: what was said, who took it, the answer."""
    ctx = {"session": {"session_id": session}}
    skill.bus.emit(Message("recognizer_loop:utterance", {"utterances": [said]}, ctx))
    if skill_id:
        skill.bus.emit(Message("ovos.intent.matched", {"skill_id": skill_id, "intent_name": intent}, ctx))
    if answer:
        skill.bus.emit(Message("speak", {"utterance": answer}, {**ctx, "skill_id": skill_id}))


def ask_what_happened(skill, session="s1"):
    ctx = {"session": {"session_id": session}}
    skill.bus.emit(Message("recognizer_loop:utterance", {"utterances": ["what just happened"]}, ctx))
    skill.handle_what_happened(Message("x", {}, ctx))
    return said(skill)


def test_what_happened_nothing(skill):
    assert "half hour" in ask_what_happened(skill)


def test_what_happened_names_the_skill_the_intent_and_the_answer(skill):
    write(skill, [])
    turn(skill, "what time is it", "ovos-skill-date-time.openvoiceos", "what_time_is_it.intent", "It's 10 past 1.")
    text = ask_what_happened(skill)
    assert "“what time is it”" in text
    assert "date time" in text and ", as what time is it" in text
    assert "It's 10 past 1." in text
    assert "Nothing left the device" in text or "Nothing was sent out" in text


def test_what_happened_says_what_went_out(skill):
    turn(skill, "tell me about bees", "ovos-skill-wikipedia.openvoiceos", "", "Bees are insects.")
    write(skill, [entry("wikipedia", "en.wikipedia.org", "ovos-skill-wikipedia", ago=0)])
    text = ask_what_happened(skill)
    assert "Wikipedia" in text and "contacted" in text


def test_what_happened_when_nobody_understood(skill):
    turn(skill, "blorp the zibble")
    text = ask_what_happened(skill)
    assert "understood it" in text and "blorp the zibble" in text


def test_what_happened_is_per_session(skill):
    turn(skill, "what time is it", "ovos-skill-date-time.openvoiceos", "", "One o'clock.", session="kitchen")
    assert "half hour" in ask_what_happened(skill, session="bedroom")
    assert "what time is it" in ask_what_happened(skill, session="kitchen")


def test_skill_and_intent_words():
    assert pkg.skill_words("ovos-skill-date-time.openvoiceos") == "date time"
    assert pkg.skill_words("skill-ovos-randomness.openvoiceos") == "randomness"
    assert pkg.intent_words("ovos-skill-x.y:what_time_is_it.intent") == "what time is it"


def test_the_log_heard_on_the_bus_counts_too(skill):
    """ovos-network-log in another container: the entries come on the bus, not in the file."""
    e = entry("wikipedia", "en.wikipedia.org", "ovos-skill-wikipedia", ago=10)
    skill.bus.emit(Message("ovos.network.request", e))
    skill.handle_sent_today(Message("x"))
    assert "Wikipedia" in said(skill)
    write(skill, [e])                      # the same request in the file too: counted once
    skill.handle_sent_today(Message("x"))
    assert "once" in said(skill) or " 1 " in said(skill)


# -- the control panel's messages ---------------------------------------------

def answer(skill, msg_type, **data):
    got = []
    skill.bus.on(f"{msg_type}.response", lambda m: got.append(Message.deserialize(m) if isinstance(m, str) else m))
    skill.bus.emit(Message(msg_type, data))
    return got[-1].data


def test_the_network_as_data(skill):
    write(skill, [entry("wikipedia", "da.wikipedia.org", "ovos-skill-wikipedia", ago=120)] * 2
          + [dict(entry("stt", "stt.openvoiceos.org", "ovos-stt-plugin-server", ago=60), blocked=True)]
          + [entry("self", "app.emkay.ai", "emkay")]
          + [entry("radio", "radio.example", "ovos-skill-radio", ago=3 * 86400)])
    data = answer(skill, pkg.GUARDIAN_NETWORK)
    assert data["has_log"] and data["total"] == 3
    wiki, stt = data["services"]
    assert (wiki["service"], wiki["count"], wiki["hosts"], wiki["who"]) == \
        ("da.wikipedia.org", 2, ["da.wikipedia.org"], ["ovos-skill-wikipedia"])
    assert (stt["kind"], stt["count"], stt["blocked"]) == ("stt", 0, 1)
    assert [e["kind"] for e in data["entries"]] == ["stt", "wikipedia", "wikipedia"], "newest first, no self"
    week = answer(skill, pkg.GUARDIAN_NETWORK, since=time.time() - 7 * 86400)
    assert {s["kind"] for s in week["services"]} == {"wikipedia", "stt", "radio"}


def test_the_network_without_a_log(skill):
    data = answer(skill, pkg.GUARDIAN_NETWORK)
    assert data["has_log"] is False and data["services"] == [] and data["entries"] == []


def test_the_status_says_who_hears_and_speaks(skill, monkeypatch):
    monkeypatch.setattr(pkg, "ANSWER_TIMEOUT", 0.2)
    skill.config_core["stt"] = {"module": "ovos-stt-plugin-vosk"}
    skill.config_core["tts"] = {"module": "ovos-tts-plugin-server"}
    write(skill, [entry("tts", "tts.example.org", "ovos-tts-plugin-server")])
    data = answer(skill, pkg.GUARDIAN_STATUS)
    assert data["stt"] == {"module": "ovos-stt-plugin-vosk", "where": "device", "hosts": []}
    assert data["tts"] == {"module": "ovos-tts-plugin-server", "where": "server", "hosts": ["tts.example.org"]}
    assert data["local_only"] is None, "no PHAL plugin: this device cannot go local only"
    phal(skill, True)
    assert answer(skill, pkg.GUARDIAN_STATUS)["local_only"] == {"enabled": True}


def test_where_speech_works():
    assert pkg.where("ovos-stt-plugin-browser", pkg.LOCAL_STT, pkg.BROWSER_STT) == "browser"
    assert pkg.where("ovos-tts-plugin-piper", pkg.LOCAL_TTS, pkg.BROWSER_TTS) == "device"
    assert pkg.where("", pkg.LOCAL_TTS, pkg.BROWSER_TTS) == ""


# -- online for one question ---------------------------------------------------

def question(skill, said="what is the weather", session="s1"):
    ctx = {"session": {"session_id": session}}
    skill._on_utterance(Message("recognizer_loop:utterance", {"utterances": [said], "lang": "en-US"}, ctx))
    return ctx


def refused(skill):
    skill._on_request(Message("ovos.network.request", {"t": int(time.time() * 1000), "host": "?",
                                                       "status": 0, "blocked": True}))


def answer_with(skill, ctx, dialog, text="Apologies."):
    skill._on_speak(Message("speak", {"utterance": text, "meta": {"dialog": dialog}}, ctx))


@pytest.fixture
def retried(skill, monkeypatch):
    """The utterances the skill asks again."""
    asked = []
    skill.bus.on("recognizer_loop:utterance",
                 lambda m: asked.append(Message.deserialize(m) if isinstance(m, str) else m))
    monkeypatch.setattr(skill, "schedule_event", lambda *a, **k: None)
    monkeypatch.setattr(skill, "cancel_scheduled_event", lambda *a, **k: None)
    monkeypatch.setattr(pkg, "REFUSAL_GRACE", 0.3)
    # settings outlive a test (they are a file); start from the default
    skill.settings["offer_online_retry"] = True
    yield asked
    skill.settings["offer_online_retry"] = True


def test_sounds_like_failure():
    assert pkg.sounds_like_failure("cant_get_forecast")
    assert pkg.sounds_like_failure("error.no.internet")
    assert not pkg.sounds_like_failure("current_weather")
    assert not pkg.sounds_like_failure(None)
    assert not pkg.sounds_like_failure("offline_on"), "Guardian's own words"


def test_offers_to_go_online_ask_again_and_go_back(skill, retried, monkeypatch):
    state = phal(skill, True)
    monkeypatch.setattr(skill, "ask_yesno", lambda *a, **k: "yes")
    ctx = question(skill)
    refused(skill)
    answer_with(skill, ctx, "cant_get_forecast")
    skill._on_handled(Message("ovos.utterance.handled", {}, ctx))
    assert not state["enabled"], "online for the question"
    assert retried and retried[-1].data["utterances"] == ["what is the weather"]
    assert retried[-1].context[pkg.RETRY_FLAG] and retried[-1].context["session"]["session_id"] == "s1"
    # the question asked again, answered online, then back offline
    skill._on_utterance(retried[-1])
    skill._on_handled(Message("ovos.utterance.handled", {}, retried[-1].context))
    assert state["enabled"] and last(skill) == "offline_again"


def test_a_skill_that_raised_counts_as_no_answer(skill, retried, monkeypatch):
    state = phal(skill, True)
    monkeypatch.setattr(skill, "ask_yesno", lambda *a, **k: "yes")
    ctx = question(skill)
    refused(skill)
    answer_with(skill, ctx, None, "An error occurred while processing a request in Weather Skill")
    skill._on_failure(Message("mycroft.skill.handler.error", {"exception": "NewConnectionError"}, ctx))
    skill._on_handled(Message("ovos.utterance.handled", {}, ctx))
    assert not state["enabled"] and retried


def test_a_refusal_reported_after_the_turn_ended_counts(skill, retried, monkeypatch):
    import threading
    state = phal(skill, True)
    monkeypatch.setattr(skill, "ask_yesno", lambda *a, **k: "yes")
    ctx = question(skill)
    skill._on_failure(Message("mycroft.skill.handler.error", {}, ctx))
    threading.Timer(0.1, refused, (skill,)).start()
    skill._on_handled(Message("ovos.utterance.handled", {}, ctx))
    assert not state["enabled"] and retried


def test_the_yes_is_not_a_turn_of_its_own(skill, retried, monkeypatch):
    """The answer to the question is taken by get_response, and OVOS sends no
    ovos.utterance.handled for it: the next handled is the retried question's."""
    state = phal(skill, True)

    def ask_yesno(*a, **k):
        skill._on_utterance(Message("recognizer_loop:utterance", {"utterances": ["yes"]}, ctx))
        return "yes"
    monkeypatch.setattr(skill, "ask_yesno", ask_yesno)
    ctx = question(skill)
    refused(skill)
    answer_with(skill, ctx, "cant_get_forecast")
    skill._on_handled(Message("ovos.utterance.handled", {}, ctx))
    skill._on_utterance(retried[-1])
    skill._on_handled(Message("ovos.utterance.handled", {}, retried[-1].context))
    assert state["enabled"] and last(skill) == "offline_again"


def test_says_no_and_stays_offline(skill, retried, monkeypatch):
    state = phal(skill, True)
    monkeypatch.setattr(skill, "ask_yesno", lambda *a, **k: "no")
    ctx = question(skill)
    refused(skill)
    skill._on_failure(Message("complete_intent_failure", {}, ctx))
    skill._on_handled(Message("ovos.utterance.handled", {}, ctx))
    assert state["enabled"] and not retried and last(skill) == "staying_offline"


@pytest.mark.parametrize("case", ["answered_locally", "nothing_refused", "not_local_only", "turned_off", "guardian_itself"])
def test_does_not_offer(skill, retried, monkeypatch, case):
    phal(skill, case != "not_local_only")
    asked = []
    monkeypatch.setattr(skill, "ask_yesno", lambda *a, **k: asked.append(1) or "yes")
    if case == "turned_off":
        skill.settings["offer_online_retry"] = False
    ctx = question(skill, "who was Lise Meitner")
    if case != "nothing_refused":
        refused(skill)
    if case == "answered_locally":
        answer_with(skill, ctx, None, "Elise Meitner was an Austrian physicist.")
    elif case == "guardian_itself":
        skill._on_matched(Message("ovos.intent.matched", {"skill_id": skill.skill_id}, ctx))
        answer_with(skill, ctx, "offline_on", "I'm offline now.")
        skill._on_failure(Message("mycroft.skill.handler.error", {}, ctx))
    else:
        skill._on_failure(Message("complete_intent_failure", {}, ctx))
    skill._on_handled(Message("ovos.utterance.handled", {}, ctx))
    assert not asked and not retried
