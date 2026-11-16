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

Without a log (an OVOS device that writes none) it says so, and answers from
the configuration alone. Settings:

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


def start_of_today() -> float:
    lt = time.localtime()
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))


#: seconds to wait for the device to answer a local only request
ANSWER_TIMEOUT = 5


class GuardianSkill(OVOSSkill):

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
        entries = read_log(self.log_path, start_of_today())
        if entries is None:
            return self.speak_dialog("no_log")
        # the site's own files (the assistant itself) are not "sent out"
        out = [e for e in entries if e.get("kind") != "self"]
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
        entries = read_log(self.log_path, start_of_today()) or []
        hosts = sorted({e.get("host", "") for e in entries if e.get("kind") == "stt"} - {""})
        if hosts:
            return self.speak_dialog("stt_remote_seen", {"module": module, "hosts": self.join(hosts)})
        self.speak_dialog("stt_remote", {"module": module or "?"})

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

    @intent_handler("are_you_online.intent")
    def handle_are_you_online(self, message: Message):
        state = self.local_only("status")
        if state is None or not state.get("enabled"):
            return self.speak_dialog("status_online")
        self.speak_dialog("status_local_only")
