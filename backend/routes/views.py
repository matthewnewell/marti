"""
The two cross-project read views behind MARTI's first two tabs: Material & Acquisition and
Routing. Each takes an optional `project_id` (the project picker) and otherwise covers every
manufacturing project in Triage rank order.
"""

from flask import Blueprint, jsonify, request

import service

bp = Blueprint("views", __name__, url_prefix="/api")


def _scope(ctx):
    pid = request.args.get("project_id") or None
    if pid and pid not in ctx["names"]:
        return None, (jsonify({"error": "not a manufacturing project MARTI knows about"}), 404)
    return pid, None


@bp.get("/acquisition")
def acquisition():
    ctx = service.context()
    pid, err = _scope(ctx)
    if err:
        return err
    return jsonify({"lines": service.acquisition_all(ctx, pid), "as_of": ctx["forecast"]["as_of"]})


@bp.get("/routing")
def routing():
    ctx = service.context()
    pid, err = _scope(ctx)
    if err:
        return err
    ids = [pid] if pid else ctx["ranking"]
    return jsonify({
        "projects": [{**service.project_row(p, ctx), "tree": service.project_tree(p, ctx)} for p in ids],
        "as_of": ctx["forecast"]["as_of"],
    })
