"""Guardian's page's API: thin relays to the skill, and to the device's
local only, over the message bus."""
import time
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel

NETWORK = "ovos.guardian.network"
STATUS = "ovos.guardian.status"
LOCAL_ONLY = "ovos.local_only"
#: the status asks the device about local only, which may take its own 5 s
TIMEOUT = 8.0
#: the periods the page offers, in days back from the start of today
PERIODS = {"today": 0, "yesterday": 1, "week": 6}


class LocalOnlyBody(BaseModel):
    enabled: bool


def ask(r, msg_type: str, data: dict | None = None, timeout: float = TIMEOUT) -> dict[str, Any] | None:
    """Send a message and give back the answer's data, or None."""
    from ovos_bus_client.message import Message
    bus = r.need_bus()
    message = Message(msg_type, data or {})
    try:
        from ovos_webui import buswait
        reply = buswait.wait_for_response(bus, message, timeout=timeout)
    except ImportError:  # an older panel: the bus client's own wait
        reply = bus.wait_for_response(message, timeout=timeout)
    return None if reply is None else reply.data


def need(answer):
    if answer is None:
        raise HTTPException(504, "Guardian did not answer; is the skill running?")
    return answer


def start_of_day(days_back: int = 0) -> float:
    lt = time.localtime()
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday - days_back, 0, 0, 0, 0, 0, -1))


def bounds(name: str) -> tuple[float, float]:
    """`since` and `until` for one of PERIODS."""
    if name not in PERIODS:
        raise HTTPException(400, "the period is one of " + ", ".join(PERIODS))
    since = start_of_day(PERIODS[name])
    until = start_of_day(0) if name == "yesterday" else time.time() + 60
    return since, until


def routes(r) -> None:
    @r.api.get("/guardian/status")
    def api_guardian_status() -> dict[str, Any]:
        return need(ask(r, STATUS))

    @r.api.get("/guardian/network")
    def api_guardian_network(period: str = "today") -> dict[str, Any]:
        since, until = bounds(period)
        return need(ask(r, NETWORK, {"since": since, "until": until}))

    # Going local only, and back online, is the device's own switch, as
    # "go offline" is by voice: an ordinary change, like the volume.
    @r.api.post("/guardian/local-only")
    def api_guardian_local_only(body: LocalOnlyBody) -> dict[str, Any]:
        answer = ask(r, LOCAL_ONLY, {"enabled": body.enabled})
        if answer is None:
            raise HTTPException(501, "this device cannot go local only")
        return {"enabled": bool(answer.get("enabled"))}
