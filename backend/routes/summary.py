"""
The Launchpad's app-summary contract for MARTI — what this app's tile shows on a project's page in
Conway's Depot (see the Depot's routes/applications.py for the proxy; it renders `headline`/
`label`/`status` opaquely and never interprets them). `project_id` is the Depot's own project id
(MARTI is Depot-aware, so the Depot passes it through unchanged).

Headline is the open routing operations (the thing that says whether work is actually moving);
the label adds open orders and, when the Tradeoff/Impact rule flags the project, the reason. A
flagged Impact is the one thing worth turning the tile yellow for.
"""

import os

from flask import Blueprint, jsonify, request

from models import Material, Tradeoff
from routes.projects import _rollup

bp = Blueprint("summary", __name__, url_prefix="/api")

FRONTEND_BASE_URL = os.environ.get("FRONTEND_BASE_URL", "http://localhost:5188")


@bp.get("/summary")
def summary():
    project_id = request.args.get("project_id")

    if not project_id:
        # Personal/portfolio-level tile: how many projects the Impact rule is flagging right now.
        flagged = sum(1 for t in Tradeoff.query.all() if t.impact()["flagged"])
        return jsonify({
            "headline": str(flagged),
            "label": "manufacturing project" + ("" if flagged == 1 else "s") + " flagged",
            "status": "warn" if flagged else "ok",
            "href": f"{FRONTEND_BASE_URL}/",
        })

    materials = Material.query.filter_by(depot_project_id=project_id).all()
    tradeoff = Tradeoff.query.filter_by(depot_project_id=project_id).first()
    href = f"{FRONTEND_BASE_URL}/projects/{project_id}"

    if not materials and tradeoff is None:
        return jsonify({"headline": None, "label": "No manufacturing data yet", "status": None, "href": href})

    roll = _rollup(materials)
    label = f"routing ops open · {roll['acquisition_orders_open']} order" + (
        "" if roll["acquisition_orders_open"] == 1 else "s"
    ) + " open"
    impact = tradeoff.impact() if tradeoff else None
    flagged = bool(impact and impact["flagged"])
    if flagged:
        label += f" · {impact['reason']}"

    return jsonify({
        "headline": str(roll["routing_ops_open"]),
        "label": label,
        "status": "warn" if flagged else "ok",
        "href": href,
    })
