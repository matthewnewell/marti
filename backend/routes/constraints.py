"""
Constraints: where work is piling up and what it would take to clear it. Per work center, what's
waiting to be processed (the queue is the main signal: count, standard hours, and days of work at
S4 available capacity), what's running, how long things have historically waited there (from past
confirmations), the forecast load over the next 10 working days, and the people it would take to
clear the queue within a week. Plus every material stopping a step from starting.

`/scenario` is the what-if sandbox: apply capacity levers (added hours, moved labor, new
equipment, outsourcing) and see every project's finish move, the same comparison Triage's preview
uses. Nothing is saved unless it's saved as a proposal.
"""

from flask import Blueprint, jsonify, request

import advisor
import scheduler
import service
from routes.proposals import validate_levers

bp = Blueprint("constraints", __name__, url_prefix="/api/constraints")


@bp.get("")
def get_constraints():
    ctx = service.context()
    return jsonify({**service.constraints(ctx), "as_of": ctx["forecast"]["as_of"], "bottleneck": ctx["bottleneck"]})


@bp.post("/scenario")
def scenario():
    body = request.get_json(force=True) or {}
    levers = body.get("levers")
    err = validate_levers(levers)
    if err:
        return jsonify({"error": err}), 400
    ctx = service.context()
    unknown = {lv.get(k) for lv in levers for k in ("work_center", "from_work_center", "to_work_center")
               if lv.get(k)} - set(ctx["snap"].work_centers)
    if unknown:
        return jsonify({"error": f"unknown work center(s): {', '.join(sorted(unknown))}"}), 400
    fc = scheduler.forecast(ctx["snap"], ctx["ranking"], ctx["need_by"], ctx["today"], ctx["now"], levers=levers)
    rows = advisor.compare(ctx["ranking"], ctx["forecast"], fc, ctx["names"])
    return jsonify({
        "projects": rows,
        "summary": advisor.summarize(rows),
        "work_centers": service.constraints(ctx, fc)["work_centers"],
    })
