"""
The Launchpad's app-summary contract for MARTI: what this app's tile shows on a project's page in
Conway's Depot (see the Depot's routes/applications.py for the proxy; it renders `headline`/
`label`/`status` opaquely and never interprets them). `project_id` is the Depot's own project id.

Headline is the Impact: days of slack to the need-by date (negative = late), or "Blocked" when S4
can't date something in the way. Late, blocked, and at-risk turn the tile yellow.
"""

import os

from flask import Blueprint, jsonify, request

import service

bp = Blueprint("summary", __name__, url_prefix="/api")

FRONTEND_BASE_URL = os.environ.get("FRONTEND_BASE_URL", "http://localhost:5188")

_WARN = ("late", "blocked", "at_risk")


@bp.get("/summary")
def summary():
    project_id = request.args.get("project_id")
    ctx = service.context()
    projects = ctx["forecast"]["projects"]

    if not project_id:
        trouble = [p for p in projects.values() if p["status"] in ("late", "blocked")]
        return jsonify({
            "headline": str(len(trouble)),
            "label": "manufacturing project" + ("" if len(trouble) == 1 else "s") + " late or blocked",
            "status": "warn" if trouble else "ok",
            "href": f"{FRONTEND_BASE_URL}/triage",
        })

    href = f"{FRONTEND_BASE_URL}/routing?project={project_id}"
    p = projects.get(project_id)
    if p is None or p["status"] == "no_orders":
        return jsonify({"headline": None, "label": "No manufacturing data yet", "status": None, "href": href})

    if p["status"] == "blocked":
        headline, label = "Blocked", p["blocker"]["reason"]
    elif p["slack_days"] is None:
        headline, label = f"#{p['rank']}", f"forecast finish {p['projected_finish']} · no need-by date set"
    else:
        s = p["slack_days"]
        headline = f"{s:+d}d"
        label = (f"{'late' if s < 0 else 'slack'} to need-by {p['need_by']} · rank #{p['rank']}")
    return jsonify({
        "headline": headline,
        "label": label,
        "status": "warn" if p["status"] in _WARN else "ok",
        "href": href,
    })
