# <img src='res/icon.png' width='50' height='50' style='vertical-align:bottom'/> Guardian

An [OpenVoiceOS](https://openvoiceos.org) skill for your privacy, by voice:
it tells what the assistant sent out on the network today and who hears
what you say, and it switches the device offline ("local only") so nothing
you say leaves it, and back online. Privacy as something you can ask about
and switch, not just a setting.

It is made for [Emkay](https://github.com/emkay-voice/emkay), OpenVoiceOS in
the browser, which keeps a log of everything it contacts (⚙ → Guardian in
its menu) and can run local only. The skill reads that log, and asks the
device's PHAL plugin to switch; other devices can answer the same messages.

## Usage

```
"What did you send out today?"   "Hvad har du sendt ud i dag?"
"Who hears what I say?"          "Hvem hører hvad jeg siger?"
"Go offline" / "Go online"       "Gå offline" / "Gå online"
"Privacy on" / "Privacy off"     "Privatliv til" / "Privatliv fra"
"Block the internet"             "Luk for internettet"
"Are you online?"                "Er du online?"
```

- **What went out today**: the services contacted today, most used first,
  with how many times ("Wikipedia 3 times, the voice 2 times and
  blog.openvoiceos.org once"). The assistant's own site files are left out:
  they are the assistant itself, not something sent out.
- **Who hears me**: where speech recognition happens. From the STT plugin
  in the configuration: on the device (Whisper, Røst, Vosk …), the
  browser's own recognition (Google in Chrome, Apple in Safari), or a
  server, named from the log when it has been used today.

In all twelve languages Emkay ships: English, Danish, German, Dutch, French,
Spanish, Italian, Portuguese (BR and PT), Catalan, Galician and Basque. The
translations other than English and Danish are in
[`tools/translations.py`](tools/translations.py), so they can be reviewed in
one place.

## The log

One JSON object per request, one per line, in
`~/.local/state/emkay/network.jsonl` (setting `log_path`):

```json
{"t": 1794863530091, "host": "stt.openvoiceos.pt", "method": "POST", "status": 200, "bytes": 52, "who": "ovos-stt-plugin-server", "kind": "stt", "service": "speech recognition (OpenVoiceOS server)"}
```

The format is described in Emkay's
[docs/network-log.md](https://github.com/emkay-voice/emkay/blob/main/docs/network-log.md).
It is not tied to Emkay: on any OpenVoiceOS install, anything that writes
these lines can feed this skill. Where nothing does, the skill says it keeps
no log, and still answers who hears you from the configuration.

Nothing in the log says what was asked: only when, which host, the method,
the status, the size and who asked.

## Local only

"Go offline", "go online" and "are you online?" switch the device to *local
only*, where nothing you say leaves it (emkay-voice/emkay#23). The skill only
asks; a PHAL plugin does the work for its hardware, so other devices can
offer the same by answering the same messages:

    ovos.local_only          {"enabled": bool}
    ovos.local_only.status   {}
    -> <type>.response       {"enabled": bool, "stt": module, "tts": module}
    ovos.local_only.changed  {"enabled": bool, "stt": module, "tts": module}

In Emkay, [ovos-phal-plugin-browser](https://github.com/emkay-voice/ovos-phal-plugin-browser)
answers them: speech recognition and the voice move into the phone, the
network layer refuses everything but Emkay's own site and the model and voice
downloads, and a small shield on the screen says it is offline. Where no PHAL
answers, the skill says this device can't switch.

## Settings

| setting | default |
|---|---|
| `log_path` | `~/.local/state/emkay/network.jsonl` |

## License

Apache-2.0
