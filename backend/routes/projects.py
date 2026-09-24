"""
MARTI's project routes: the manufacturing-project list and one project's detail (Material
Acquisition, Routing, Impact). Project names come from Conway's Depot (federated, never copied);
everything else is mocked S4 plus MARTI's own Triage ranking, assembled in service.py.
"""

from flask import Blueprint, jsonify

import service

bp = Blueprint("projects", __name__, url_prefix="/api/projects")


@bp.get("")
def list_manufacturing_projects():
    """Depot being unreachable is a normal degraded state (names come back null), not an error,
    same as every other depot_client caller in this ecosystem."""
    ctx = service.context()
    return jsonify({
        "projects": [service.project_row(pid, ctx) for pid in ctx["ranking"]],
        "depot_reachable": ctx["depot_reachable"],
        "as_of": ctx["forecast"]["as_of"],
    })


@bp.get("/<depot_project_id>")
def get_project_detail(depot_project_id):
    ctx = service.context()
    if depot_project_id not in ctx["names"]:
        return jsonify({"error": "not a manufacturing project MARTI knows about"}), 404
    return jsonify(service.project_detail(depot_project_id, ctx))
