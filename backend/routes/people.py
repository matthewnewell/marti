"""
Proxies Conway's Depot's own persona list for MARTI's "viewing as" user menu, the same menu every
sibling app shows. Server-to-server, so the frontend only ever talks to this app's own backend.
Not authentication: nothing in the ecosystem is access-controlled. The persona is who MARTI
credits a commit, decision or Journal entry to.
"""

from flask import Blueprint, jsonify

import depot_client

bp = Blueprint("people", __name__, url_prefix="/api")


@bp.get("/people")
def list_people():
    people = depot_client.fetch_people()
    if people is None:
        return jsonify({"people": [], "depot_reachable": False})
    return jsonify({"people": people, "depot_reachable": True})
