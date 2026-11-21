"""Guardian's page in ovos-control-panel: privacy you can see.

The control panel finds this page through the ``opm.control_panel.page``
entry point (see pyproject.toml and the panel's docs/pages.md). It shows who
hears what you say and who speaks, switches the device to local only and
back, and shows what the assistant sent out on the network, service by
service and request by request. Nothing here is loaded by the skill itself,
so the skill needs no web packages; the panel brings those.
"""


def routes(r):
    # Imported here, so reading PAGE (the panel's registry, this skill's
    # tests) needs no web framework; only the panel calls this.
    from ovos_skill_guardian.panel.api import routes as add
    add(r)


PAGE = {
    "api_version": 1,
    "id": "guardian",
    "path": "/privacy",
    "title": {"key": "guardian.title", "label": "Privacy"},
    # something most people want to see: with the everyday pages, after Network (50)
    "group": "everyday",
    "order": 55,
    "needs": ["ovos-skill-guardian"],
    "html": "page.html",
    "icon": "icon.svg",
    "i18n": "i18n",
    "routes": routes,
}
