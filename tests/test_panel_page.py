"""Guardian's page in ovos-control-panel: its description, its strings in
every language the skill speaks, and its routes talking to the skill."""
import json
import re
import time
from pathlib import Path

import pytest

import test_skill
from test_skill import entry, phal, skill, write  # noqa: F401 - skill is a fixture

pkg = test_skill.pkg
from ovos_skill_guardian import panel  # noqa: E402 - after the package is loaded

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "panel"
LANGS = {p.name.split("-")[0] for p in (ROOT / "locale").iterdir() if p.is_dir()}


def test_the_page_description_names_files_that_exist():
    page = panel.PAGE
    assert page["api_version"] == 1 and page["id"] == "guardian"
    for key in ("html", "icon"):
        assert (PANEL / page[key]).is_file(), key
    assert callable(page["routes"]) and page["group"] == "everyday"


def test_the_page_speaks_every_language_the_skill_does():
    files = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in (PANEL / "i18n").glob("*.json")}
    assert LANGS <= set(files)
    keys = set(files["en"])
    for lang, table in files.items():
        assert set(table) == keys, lang
        assert all(text.strip() for text in table.values()), lang
        assert "{n}" in table["guardian.net.sum"] and "{s}" in table["guardian.net.sum"], lang
    html = (PANEL / "page.html").read_text(encoding="utf-8")
    used = set(re.findall(r'data-i18n="([^"]+)"', html)) | set(re.findall(r'\bt\("([^"]+)"', html)) \
        | set(re.findall(r"aria-label:([\w.]+)", html))
    dynamic = {k for k in used if k.endswith(".")}
    assert used - dynamic <= keys, "a string the page uses has no translation"
    for prefix, names in (("guardian.kind.", pkg.KINDS), ("guardian.where.", ("device", "browser", "server", "none"))):
        assert {prefix + n for n in names} <= keys


# ── the routes, against the skill itself on a bus ────────────────────────────
pytest.importorskip("fastapi")
pytest.importorskip("httpx")


@pytest.fixture
def client(skill):  # noqa: F811 - the fixture
    from fastapi import APIRouter, FastAPI
    from fastapi.testclient import TestClient

    class R:
        api = APIRouter(prefix="/api")
        privileged = APIRouter(prefix="/api")
        config = None

        @staticmethod
        def need_bus():
            return skill.bus

    panel.routes(R)
    app = FastAPI()
    app.include_router(R.api)
    app.include_router(R.privileged)
    with TestClient(app) as c:
        yield c, skill


def test_what_went_out_today_and_this_week(client):
    c, skill = client
    write(skill, [entry("wikipedia", "da.wikipedia.org", "ovos-skill-wikipedia")]
          + [entry("radio", "radio.example", "ovos-skill-radio", ago=3 * 86400)])
    today = c.get("/api/guardian/network").json()
    assert [s["kind"] for s in today["services"]] == ["wikipedia"]
    week = c.get("/api/guardian/network", params={"period": "week"}).json()
    assert {s["kind"] for s in week["services"]} == {"wikipedia", "radio"}
    assert c.get("/api/guardian/network", params={"period": "ever"}).status_code == 400


def test_yesterday_stops_at_midnight(client):
    from ovos_skill_guardian.panel import api
    since, until = api.bounds("yesterday")
    assert until == api.start_of_day(0) and 22 * 3600 < until - since < 26 * 3600


def test_the_status_and_the_switch(client, monkeypatch):
    c, skill = client
    monkeypatch.setattr(pkg, "ANSWER_TIMEOUT", 0.2)
    skill.config_core["stt"] = {"module": "ovos-stt-plugin-server"}
    assert c.get("/api/guardian/status").json()["local_only"] is None
    from ovos_skill_guardian.panel import api
    monkeypatch.setattr(api, "TIMEOUT", 0.3)
    assert c.post("/api/guardian/local-only", json={"enabled": True}).status_code == 501
    state = phal(skill, False)
    assert c.post("/api/guardian/local-only", json={"enabled": True}).json() == {"enabled": True}
    assert state["enabled"] is True
    status = c.get("/api/guardian/status").json()
    assert status["local_only"] == {"enabled": True} and status["stt"]["where"] == "server"
