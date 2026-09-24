"""
Hot flags: expedite requests MARTI raised when a Triage re-rank moved a project up (see
routes/tradeoffs.py). There's no create route: flags come only from leadership's ranking. The
owner acknowledges with a typed name, then resolves once the blocker is cleared.
"""

from flask import Blueprint, jsonify, request

import depot_client
from db import db
from models import FLAG_STATUSES, HotFlag, _now

bp = Blueprint("hot_flags", __name__, url_prefix="/api/hot-flags")


@bp.get("")
def list_flags():
    q = HotFlag.query
    status = request.args.get("status")
    if status == "active":
        q = q.filter(HotFlag.status != "resolved")
    elif status in FLAG_STATUSES:
        q = q.filter(HotFlag.status == status)
    if request.args.get("project_id"):
        q = q.filter(HotFlag.depot_project_id == request.args["project_id"])
    flags = q.order_by(HotFlag.raised_at.desc()).all()

    names = {p["id"]: p["name"] for p in (depot_client.fetch_projects() or [])}
    return jsonify({"hot_flags": [{**f.to_dict(), "project_name": names.get(f.depot_project_id)} for f in flags]})


@bp.post("/<flag_id>/acknowledge")
def acknowledge(flag_id):
    flag = db.session.get(HotFlag, flag_id)
    if flag is None:
        return jsonify({"error": "hot flag not found"}), 404
    name = ((request.get_json(force=True) or {}).get("name") or "").strip()
    if not name:
        return jsonify({"error": "type your name to acknowledge"}), 400
    if flag.status != "open":
        return jsonify({"error": f"flag is already {flag.status}"}), 400
    flag.status = "acknowledged"
    flag.acknowledged_by = name
    flag.acknowledged_at = _now()
    db.session.commit()
    return jsonify(flag.to_dict())


@bp.post("/<flag_id>/resolve")
def resolve(flag_id):
    flag = db.session.get(HotFlag, flag_id)
    if flag is None:
        return jsonify({"error": "hot flag not found"}), 404
    if flag.status == "resolved":
        return jsonify({"error": "flag is already resolved"}), 400
    flag.status = "resolved"
    flag.resolved_at = _now()
    db.session.commit()
    return jsonify(flag.to_dict())
