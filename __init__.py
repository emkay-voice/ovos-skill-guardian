"""Guardian: what the assistant sent out, and who hears what you say.

Reads a network log, one JSON object per request (the format Emkay writes,
see https://github.com/emkay-voice/emkay/blob/main/docs/network-log.md):

    {"t": <ms since 1970>, "host": "...", "method": "GET", "status": 200,
     "bytes": 1234, "who": "ovos-skill-wikipedia", "kind": "wikipedia",
     "service": "Wikipedia"}

and answers:

- "what did you send out today?": the services contacted today, most used
  first, with how many times
- "who hears what I say?": where speech recognition happens, from the STT
  plugin in the configuration and the log
- "what just happened?": the last thing you said, which skill took it (and
  with which intent), what it answered, and what went out meanwhile – a
  spoken version of what ovos-tui-client and Emkay's What's happening? show.
  It follows the bus, which every OVOS has: recognizer_loop:utterance, the
  ovos.intent.matched notification and who spoke (speak's skill_id); the
  network part needs the log
- "go offline", "go online", "are you online?": "local only", where nothing
  leaves the device. The device does it and answers on the bus:

      ovos.local_only         {"enabled": bool}
      ovos.local_only.status  {}
      -> <type>.response               {"enabled": bool, "stt": module, "tts": module}

  The messages are hardware-neutral: a PHAL plugin answers them for its
  device. In Emkay that is ovos-phal-plugin-browser (speech recognition and
  voice on the phone, the network refused but for its own site and model
  downloads, a shield on the screen); on other hardware another PHAL plugin
  can do the same. Without an answer the skill says this device can't.

For a control-panel page (panel/), the same as data on the bus:

    ovos.guardian.network  {"since": s, "until": s, "limit": n}
    ovos.guardian.status   {}
    -> <type>.response     (see handle_network and handle_status)

On an ordinary OVOS device, ovos-network-log writes the same log (and sends
each entry on the bus as ovos.network.request, which this skill hears too –
across Docker containers, where the file is not shared). Without a log it
says so, and answers from the configuration alone. Settings:

    log_path   where the log is (default ~/.local/state/emkay/network.jsonl)
"""
import json
import os
import time
from collections import Counter

from ovos_bus_client.message import Message
from ovos_utils import classproperty
from ovos_utils.process_utils import RuntimeRequirements
from ovos_workshop.decorators import intent_handler
from ovos_workshop.skills import OVOSSkill

DEFAULT_LOG = "~/.local/state/emkay/network.jsonl"

#: services with a name of their own in the dialogs (kind_<kind>.dialog)
KINDS = ("stt", "tts", "translate", "wikipedia", "models", "store", "packages",
         "pyodide", "github", "weather", "radio")

#: speech recognition that stays on the device
LOCAL_STT = ("ovos-stt-plugin-whisper-browser", "ovos-stt-plugin-fasterwhisper",
             "ovos-stt-plugin-whispercpp", "ovos-stt-plugin-vosk", "ovos-stt-plugin-nemo",
             "ovos-stt-plugin-citrinet", "ovos-stt-plugin-wav2vec", "ovos-stt-plugin-chromium-local")
#: the browser's own speech recognition (Web Speech API)
BROWSER_STT = ("ovos-stt-plugin-browser",)
#: voices made on the device
LOCAL_TTS = ("ovos-tts-plugin-piper", "ovos-tts-plugin-piper-browser", "ovos-tts-plugin-mimic",
             "ovos-tts-plugin-espeakng", "ovos-tts-plugin-espeak", "ovos-tts-plugin-pico",
             "ovos-tts-plugin-sam", "ovos-tts-plugin-beepspeak", "ovos-tts-plugin-dummy",
             "ovos-tts-plugin-kokoro", "ovos-tts-plugin-matxa-multispeaker-cat")
#: the browser's own voices (Web Speech API)
BROWSER_TTS = ("ovos-tts-plugin-browser",)

#: the messages behind the control panel's page
GUARDIAN_NETWORK = "ovos.guardian.network"
GUARDIAN_STATUS = "ovos.guardian.status"
GUARDIAN_LOCAL_ONLY = "ovos.guardian.local_only"
#: the periods the control panel's page offers, in days back from today
PERIODS = {"today": 0, "yesterday": 1, "week": 6}
#: the most requests one answer lists (the summary counts them all)
MAX_ENTRIES = 1000
PAGE_ENTRIES = 200


def where(module: str, local: tuple, browser: tuple) -> str:
    """Where a speech plugin does its work: "device", "browser" or "server"
    ("" when none is set)."""
    if not module:
        return ""
    if module in local:
        return "device"
    if module in browser:
        return "browser"
    return "server"


def summarize(entries: list) -> list:
    """The services in `entries`, most used first: kind, service, how many
    times, the hosts, when last, and how many were refused (local only)."""
    out = {}
    for e in entries:
        key = (e.get("kind") or "", e.get("service") or e.get("host") or "?")
        s = out.setdefault(key, {"kind": key[0], "service": key[1], "count": 0, "blocked": 0,
                                 "hosts": set(), "who": set(), "last": 0})
        if e.get("blocked"):
            s["blocked"] += 1
        else:
            s["count"] += 1
        if e.get("host"):
            s["hosts"].add(e["host"])
        if e.get("who"):
            s["who"].add(e["who"])
        s["last"] = max(s["last"], e.get("t", 0))
    rows = [dict(s, hosts=sorted(s["hosts"]), who=sorted(s["who"])) for s in out.values()]
    return sorted(rows, key=lambda r: (-r["count"], -r["blocked"], r["service"]))


def read_log(path: str, since: float = 0) -> list:
    """The log's entries since `since` (seconds since 1970); None without a log."""
    try:
        with open(os.path.expanduser(path), encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return None
    out = []
    for line in lines:
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if isinstance(e, dict) and e.get("t", 0) / 1000 >= since:
            out.append(e)
    return out


def start_of_today(days_back: int = 0) -> float:
    lt = time.localtime()
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday - days_back, 0, 0, 0, 0, 0, -1))


def period_bounds(name) -> tuple:
    """`since` and `until` for one of PERIODS; today for any other."""
    until = start_of_today() if name == "yesterday" else time.time() + 60
    return start_of_today(PERIODS.get(name, 0)), until


#: seconds to wait for the device to answer a local only request
ANSWER_TIMEOUT = 5


#: the turn before "what just happened?" is forgotten after this long (s)
TURN_MEMORY = 30 * 60

#: marks a question asked again online, in the utterance's context
RETRY_FLAG = "guardian_retry"
#: back to local only after this long (s), even if the retried question never ends
RETRY_TIMEOUT = 60
#: how long after a turn without an answer a refused connection may still be reported (s)
REFUSAL_GRACE = 2
#: words in a dialog's name that mean "I could not" (cant_get_forecast, error_no_internet …)
FAILURE_WORDS = ("cant", "cannot", "can_not", "unable", "error", "fail", "unavailable",
                 "not_available", "no_internet", "no_network", "no_connection", "offline")


def sounds_like_failure(dialog: str) -> bool:
    """Whether a dialog's name says the skill could not answer."""
    name = (dialog or "").lower().replace("-", "_").replace(".", "_").replace(" ", "_")
    return any(word in name for word in FAILURE_WORDS)


def skill_words(skill_id: str) -> str:
    """A skill id said aloud: ovos-skill-date-time.openvoiceos -> date time."""
    name = (skill_id or "").split(".")[0]
    for prefix in ("ovos-skill-", "skill-ovos-", "skill-", "ovos-"):
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    return name.replace("-", " ").replace("_", " ").strip()


def intent_words(intent: str) -> str:
    """An intent name said aloud: what_time_is_it.intent -> what time is it."""
    name = (intent or "").split(":")[-1]
    for suffix in (".intent", ".voc"):
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    return name.replace("_", " ").replace("-", " ").strip()


class GuardianSkill(OVOSSkill):

    def initialize(self):
        # what just happened: per session, the turn going on and the one before
        self.turns = {}
        self.add_event("recognizer_loop:utterance", self._on_utterance, speak_errors=False)
        self.add_event("ovos.intent.matched", self._on_matched, speak_errors=False)
        self.add_event("speak", self._on_speak, speak_errors=False)
        # the network log as it happens, from ovos-network-log in any OVOS
        # process or container (the file may be in another container)
        self.heard = []
        self.add_event("ovos.network.request", self._on_request, speak_errors=False)
        # local only and a question that needed the internet: offer to go
        # online for that one question, ask it again, and go back offline
        self.add_event("complete_intent_failure", self._on_failure, speak_errors=False)
        # a skill's handler that raised (its "An error occurred …" has no dialog name)
        self.add_event("mycroft.skill.handler.error", self._on_failure, speak_errors=False)
        self.add_event("ovos.utterance.handled", self._on_handled, speak_errors=False)
        # the control panel's page
        self.add_event(GUARDIAN_NETWORK, self.handle_network, speak_errors=False)
        self.add_event(GUARDIAN_STATUS, self.handle_status, speak_errors=False)
        self.add_event(GUARDIAN_LOCAL_ONLY, self.handle_local_only, speak_errors=False)

    def _on_request(self, message):
        self.heard.append(dict(message.data))
        cutoff = (time.time() - 86400 * 2) * 1000
        if len(self.heard) > 5000 or (self.heard and self.heard[0].get("t", 0) < cutoff):
            self.heard = [e for e in self.heard[-5000:] if e.get("t", 0) >= cutoff]
        # refused (local only) or never answered: count it for the turns going on
        entry = message.data
        if entry.get("blocked") or entry.get("status") == 0:
            for s in self.turns.values():
                now = s.get("now")
                if now and entry.get("t", 0) / 1000 >= now["t"] - 1:
                    now["refused"] += 1

    def network_log(self, since: float = 0):
        """The network log since `since`: the file, and what was heard on the
        bus (ovos-network-log), each request once; None when there is neither."""
        entries = read_log(self.log_path, since)
        if entries is None and not self.heard:
            return None
        seen = {(e.get("t"), e.get("host"), e.get("method")) for e in entries or []}
        more = [e for e in self.heard if e.get("t", 0) >= since * 1000
                and (e.get("t"), e.get("host"), e.get("method")) not in seen]
        return sorted((entries or []) + more, key=lambda e: e.get("t", 0))

    @staticmethod
    def _session(message) -> str:
        return ((message.context or {}).get("session") or {}).get("session_id", "default")

    def _on_utterance(self, message):
        utt = (message.data.get("utterances") or [""])[0]
        s = self.turns.setdefault(self._session(message), {})
        if s.get("now"):
            s["before"] = s["now"]
        s["now"] = {"said": utt, "t": time.time(), "skill": "", "intent": "", "answers": [],
                    "dialogs": [], "refused": 0, "failed": False, "message": message,
                    "retry": bool((message.context or {}).get(RETRY_FLAG))}

    def _on_matched(self, message):
        now = self.turns.get(self._session(message), {}).get("now")
        if now is not None:
            now["skill"] = message.data.get("skill_id") or now["skill"]
            now["intent"] = message.data.get("intent_name") or message.data.get("intent_type") or ""

    def _on_speak(self, message):
        now = self.turns.get(self._session(message), {}).get("now")
        if now is not None:
            now["answers"].append(message.data.get("utterance", ""))
            now["dialogs"].append((message.data.get("meta") or {}).get("dialog") or "")
            if not now["skill"]:
                now["skill"] = (message.context or {}).get("skill_id", "")

    @classproperty
    def runtime_requirements(self):
        return RuntimeRequirements(internet_before_load=False,
                                   network_before_load=False,
                                   gui_before_load=False,
                                   requires_internet=False,
                                   requires_network=False,
                                   requires_gui=False,
                                   no_internet_fallback=True,
                                   no_network_fallback=True,
                                   no_gui_fallback=True)

    @property
    def log_path(self) -> str:
        return self.settings.get("log_path") or DEFAULT_LOG

    # -- words ---------------------------------------------------------------

    def service_name(self, entry: dict) -> str:
        """A service in this language: kind_<kind>.dialog, else the log's words."""
        kind = entry.get("kind")
        if kind in KINDS:
            return self.dialog_renderer.render(f"kind_{kind}")
        return entry.get("service") or entry.get("host") or "?"

    def join(self, items: list) -> str:
        """'a, b and c' in this language."""
        if len(items) <= 1:
            return "".join(items)
        word = self.dialog_renderer.render("and")
        return f"{', '.join(items[:-1])} {word} {items[-1]}"

    def show(self, text: str):
        if self.gui.connected:
            self.gui.show_text(text, title="Guardian", override_idle=20)

    # -- what went out today -------------------------------------------------

    @intent_handler("sent_today.intent")
    def handle_sent_today(self, message: Message):
        entries = self.network_log(start_of_today())
        if entries is None:
            return self.speak_dialog("no_log")
        # the site's own files (the assistant itself) are not "sent out", nor
        # are requests refused in local only ("blocked": they never left)
        out = [e for e in entries if e.get("kind") != "self" and not e.get("blocked")]
        if not out:
            return self.speak_dialog("sent_nothing")
        counts = Counter(self.service_name(e) for e in out)
        top = counts.most_common(5)
        parts = [self.dialog_renderer.render("times" if n != 1 else "times_one", {"service": s, "count": n})
                 for s, n in top]
        data = {"count": len(counts), "list": self.join(parts)}
        dialog = "sent_today_more" if len(counts) > len(top) else "sent_today"
        data["rest"] = len(counts) - len(top)
        self.speak_dialog(dialog, data)
        self.show("\n".join(f"{s}: {n}" for s, n in counts.most_common()))

    # -- who hears me --------------------------------------------------------

    @intent_handler("who_hears_me.intent")
    def handle_who_hears_me(self, message: Message):
        module = (self.config_core.get("stt") or {}).get("module", "")
        if module in LOCAL_STT:
            return self.speak_dialog("stt_local", {"module": module})
        if module in BROWSER_STT:
            return self.speak_dialog("stt_browser")
        entries = self.network_log(start_of_today()) or []
        hosts = sorted({e.get("host", "") for e in entries
                        if e.get("kind") == "stt" and not e.get("blocked")} - {""})
        if hosts:
            return self.speak_dialog("stt_remote_seen", {"module": module, "hosts": self.join(hosts)})
        self.speak_dialog("stt_remote", {"module": module or "?"})

    # -- what just happened -------------------------------------------------

    def last_turn(self, message):
        """The turn before this question (this one is the question itself)."""
        s = self.turns.get(self._session(message), {})
        turn = s.get("before")
        if not turn or time.time() - turn["t"] > TURN_MEMORY:
            return None
        return turn

    @intent_handler("what_happened.intent")
    def handle_what_happened(self, message: Message):
        turn = self.last_turn(message)
        if not turn:
            return self.speak_dialog("happened_nothing")
        parts = [self.dialog_renderer.render("happened_heard", {"said": turn["said"]})]
        if turn["skill"] and turn["skill"] != self.skill_id:
            data = {"skill": skill_words(turn["skill"]), "intent": intent_words(turn["intent"])}
            parts.append(self.dialog_renderer.render("happened_skill_intent" if data["intent"] else "happened_skill", data))
        else:
            parts.append(self.dialog_renderer.render("happened_nobody"))
        if turn["answers"]:
            answer = turn["answers"][0].strip()
            if answer and answer[-1] not in ".!?…\"”»":
                answer += "."
            parts.append(self.dialog_renderer.render("happened_answered", {"answer": answer}))
        # what went out meanwhile: the network log between that turn and this question
        entries = self.network_log(turn["t"] - 1)
        if entries is not None:
            until = (self.turns.get(self._session(message), {}).get("now") or {}).get("t", time.time())
            out = [e for e in entries if e.get("kind") != "self" and not e.get("blocked")
                   and e.get("t", 0) / 1000 <= until]
            services = sorted({self.service_name(e) for e in out})
            parts.append(self.dialog_renderer.render("happened_sent", {"list": self.join(services)})
                         if services else self.dialog_renderer.render("happened_sent_nothing"))
        text = " ".join(p.strip() for p in parts if p.strip())
        self.speak(text)
        self.show(text)

    # -- local only ----------------------------------------------------------

    def local_only(self, what: str = "", **data):
        """Ask the device (ovos.local_only[.what]); its answer or None."""
        msg_type = "ovos.local_only" + (f".{what}" if what else "")
        reply = self.bus.wait_for_response(Message(msg_type, data), f"{msg_type}.response",
                                           timeout=ANSWER_TIMEOUT)
        return reply.data if reply else None

    @intent_handler("go_offline.intent")
    def handle_go_offline(self, message: Message):
        state = self.local_only(enabled=True)
        if state is None:
            return self.speak_dialog("no_local_only")
        self.speak_dialog("offline_on")

    @intent_handler("go_online.intent")
    def handle_go_online(self, message: Message):
        state = self.local_only(enabled=False)
        if state is None:
            return self.speak_dialog("no_local_only")
        self.speak_dialog("offline_off")

    # -- online for one question ----------------------------------------------

    def _on_failure(self, message):
        now = self.turns.get(self._session(message), {}).get("now")
        if now is not None:
            now["failed"] = True

    def needed_the_internet(self, turn: dict) -> bool:
        """Something tried to go out and was refused, and there was no real
        answer: nobody understood, nothing was said, or the skill said it
        could not (its dialog's name, e.g. cant_get_forecast). A question
        answered from what is on the device (offline wiki) is left alone."""
        no_answer = turn["failed"] or not turn["answers"] or any(map(sounds_like_failure, turn["dialogs"]))
        if not no_answer:
            return False
        # the refusal can be reported a moment after the turn ended (the
        # device reports refused connections as it sees them): give it time
        deadline = time.time() + REFUSAL_GRACE
        while not turn["refused"] and time.time() < deadline:
            time.sleep(0.1)
        return bool(turn["refused"])

    def _on_handled(self, message):
        session = self._session(message)
        turn = self.turns.get(session, {}).get("now")
        if not turn or turn.get("done"):
            return
        turn["done"] = True
        if turn["retry"]:
            self.cancel_scheduled_event(f"guardian_offline_{session}")
            self.back_offline()
            return
        if not self.settings.get("offer_online_retry", True) or not self.needed_the_internet(turn):
            return
        state = self.local_only("status")
        if not state or not state.get("enabled"):
            return  # not local only: a real network problem, not ours to solve
        if self.ask_yesno("retry_online") != "yes":
            return self.speak_dialog("staying_offline")
        if self.local_only(enabled=False) is None:
            return self.speak_dialog("no_local_only")
        original = turn["message"]
        context = dict(original.context or {}, **{RETRY_FLAG: True})
        # whatever happens to the question, the device goes back offline
        self.schedule_event(self.back_offline, RETRY_TIMEOUT, name=f"guardian_offline_{session}")
        self.bus.emit(Message("recognizer_loop:utterance", dict(original.data), context))

    def back_offline(self, message=None):
        if self.local_only(enabled=True) is not None:
            self.speak_dialog("offline_again")

    # -- the same, as data, for the control panel's page --------------------

    def handle_network(self, message: Message):
        """What went out in a `period` (today, yesterday or week), or between
        `since` and `until` (seconds since 1970; the start of today and now
        by default): the services, and the requests themselves, newest
        first. The assistant's own files ("self") are left out, as when it
        is asked aloud."""
        since, until = period_bounds(message.data.get("period"))
        since = float(message.data.get("since") or since)
        until = float(message.data.get("until") or until)
        # the page asks by period, and shows the newest PAGE_ENTRIES
        default = PAGE_ENTRIES if message.data.get("period") else MAX_ENTRIES
        limit = max(1, min(int(message.data.get("limit") or default), MAX_ENTRIES))
        entries = self.network_log(since)
        data = {"has_log": entries is not None, "log_path": self.log_path,
                "since": since, "until": until, "services": [], "entries": [], "total": 0,
                "refused": 0, "service_count": 0, "nothing": False}
        if entries is not None:
            entries = [e for e in entries if e.get("kind") != "self" and e.get("t", 0) / 1000 <= until]
            services = summarize(entries)
            # the times in seconds, as the page shows them
            data["services"] = [dict(s, key=f"{s['kind']}:{s['service']}", last_s=s["last"] / 1000)
                                for s in services]
            data["total"] = len(entries)
            data["refused"] = sum(s["blocked"] for s in services)
            data["service_count"] = len(services)
            data["nothing"] = not entries
            keep = ("t", "host", "method", "status", "bytes", "who", "kind", "service", "blocked")
            data["entries"] = [dict({k: e[k] for k in keep if k in e}, id=str(n), when=e.get("t", 0) / 1000,
                                    blocked=bool(e.get("blocked")))
                               for n, e in enumerate(reversed(entries[-limit:]))]
        self.bus.emit(message.response(data))

    def handle_status(self, message: Message):
        """Who hears and who speaks (the plugin, and where it works), the
        servers speech went to today, and local only: its state, or None
        when this device cannot go local only."""
        stt = (self.config_core.get("stt") or {}).get("module", "")
        tts = (self.config_core.get("tts") or {}).get("module", "")
        today = self.network_log(start_of_today()) or []
        seen = {kind: sorted({e.get("host", "") for e in today
                              if e.get("kind") == kind and not e.get("blocked")} - {""})
                for kind in ("stt", "tts")}
        state = self.local_only("status")
        enabled = bool(state and state.get("enabled"))
        hears = where(stt, LOCAL_STT, BROWSER_STT)
        speaks = where(tts, LOCAL_TTS, BROWSER_TTS)
        self.bus.emit(message.response({
            "stt": {"module": stt, "where": hears, "hosts": seen["stt"]},
            "tts": {"module": tts, "where": speaks, "hosts": seen["tts"]},
            "local_only": None if state is None else {"enabled": enabled},
            "has_log": self.network_log(start_of_today()) is not None,
            # the same, as the page shows it: a word per state, and yes/no
            "hears": hears or "none", "speaks": speaks or "none",
            "hears_browser": hears == "browser", "hears_server": hears == "server",
            "speaks_browser": speaks == "browser", "speaks_server": speaks == "server",
            "local": "unknown" if state is None else ("on" if enabled else "off"),
            "can_go_offline": state is not None and not enabled,
            "can_go_online": enabled, "cannot_switch": state is None,
        }))

    def handle_local_only(self, message: Message):
        """Local only on or off, from the control panel's page: the device's
        own switch, as "go offline" is by voice."""
        state = self.local_only(enabled=bool(message.data.get("enabled")))
        if state is None:
            self.bus.emit(message.response({"error": "guardian.local.cannot"}))
            return
        self.bus.emit(message.response({"enabled": bool(state.get("enabled"))}))

    @intent_handler("are_you_online.intent")
    def handle_are_you_online(self, message: Message):
        state = self.local_only("status")
        if state is None or not state.get("enabled"):
            return self.speak_dialog("status_online")
        self.speak_dialog("status_local_only")
