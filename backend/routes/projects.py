"""
MARTI's own project-scoped routes — the manufacturing-project list, one project's detail, and
the Tradeoff (priority + due date) editor. Every project fact itself comes from Conway's Depot
(depot_client, federated, never copied); this app only ever stores Material/AcquisitionOrder/
Routing (mocked S4) and Tradeoff (this app's own).
"""

from datetime import date as date_cls

from flask import Blueprint, jsonify, request

import depot_client
from db import db
from models import PRIORITIES, Material, Tradeoff

bp = Blueprint("projects", __name__, url_prefix="/api/projects")

# In-house production or both — the other half of the hybrid manufacturing-project trigger
# alongside Conway's Depot's own Project.has_manufacturing (see models.py's module docstring).
_MANUFACTURING_PROCUREMENT_TYPES = ("E", "X")


def _manufacturing_project_ids_from_materials() -> set[str]:
    rows = (
        db.session.query(Material.depot_project_id)
        .filter(Material.procurement_type.in_(_MANUFACTURING_PROCUREMENT_TYPES))
        .distinct()
        .all()
    )
    return {r[0] for r in rows}


def _tradeoff_by_project() -> dict[str, Tradeoff]:
    return {t.depot_project_id: t for t in Tradeoff.query.all()}


def _rollup(materials: list[Material]) -> dict:
    """Coarse counts for the list view — how many acquisition orders / routing operations are
    open vs. done, across every material this project has. Detail lives on the project page;
    this is just enough to scan a whole list at a glance."""
    orders_open = orders_total = ops_open = ops_total = 0
    for m in materials:
        for a in m.acquisition_orders:
            orders_total += 1
            if a.status != "received":
                orders_open += 1
        for r in m.routings:
            ops_total += 1
            if r.status not in ("complete",):
                ops_open += 1
    return {
        "acquisition_orders_open": orders_open,
        "acquisition_orders_total": orders_total,
        "routing_ops_open": ops_open,
        "routing_ops_total": ops_total,
    }


@bp.get("")
def list_manufacturing_projects():
    """The hybrid filter: a project qualifies if Conway's Depot says has_manufacturing=true,
    OR it has at least one mocked material master with procurement type E/X — see this
    module's docstring and models.py's for the full reasoning. Depot being unreachable is a
    normal degraded state (empty list), not an error, same as every other depot_client caller
    in this ecosystem."""
    depot_projects = depot_client.fetch_projects()
    if depot_projects is None:
        return jsonify({"projects": [], "depot_reachable": False})

    material_trigger_ids = _manufacturing_project_ids_from_materials()
    tradeoff_by_project = _tradeoff_by_project()

    out = []
    for p in depot_projects:
        if not (p.get("has_manufacturing") or p["id"] in material_trigger_ids):
            continue
        materials = Material.query.filter_by(depot_project_id=p["id"]).all()
        tradeoff = tradeoff_by_project.get(p["id"])
        out.append({
            "depot_project_id": p["id"],
            "name": p["name"],
            "has_manufacturing": p.get("has_manufacturing"),
            "manufacturing_source": (
                "depot" if p.get("has_manufacturing") else "material"
            ),
            "tradeoff": tradeoff.to_dict() if tradeoff else None,
            **_rollup(materials),
        })
    return jsonify({"projects": out, "depot_reachable": True})


@bp.get("/<depot_project_id>")
def get_project_detail(depot_project_id):
    project = depot_client.fetch_project(depot_project_id)
    if project is None:
        return jsonify({"error": "project not found on the Depot, or the Depot is unreachable"}), 404

    materials = Material.query.filter_by(depot_project_id=depot_project_id).all()
    tradeoff = Tradeoff.query.filter_by(depot_project_id=depot_project_id).first()

    return jsonify({
        "depot_project_id": depot_project_id,
        "name": project["name"],
        "has_manufacturing": project.get("has_manufacturing"),
        "materials": [m.to_dict() for m in materials],
        "tradeoff": tradeoff.to_dict() if tradeoff else None,
    })


@bp.put("/<depot_project_id>/tradeoff")
def upsert_tradeoff(depot_project_id):
    body = request.get_json(force=True) or {}

    priority = body.get("priority")
    if priority is not None and priority not in PRIORITIES:
        return jsonify({"error": f"priority must be one of {PRIORITIES}"}), 400

    due_date = None
    if body.get("due_date"):
        try:
            due_date = date_cls.fromisoformat(body["due_date"])
        except ValueError:
            return jsonify({"error": "due_date must be an ISO date (YYYY-MM-DD)"}), 400

    tradeoff = Tradeoff.query.filter_by(depot_project_id=depot_project_id).first()
    if tradeoff is None:
        tradeoff = Tradeoff(depot_project_id=depot_project_id, priority=priority or "medium")
        db.session.add(tradeoff)
    elif priority is not None:
        tradeoff.priority = priority
    if "due_date" in body:
        tradeoff.due_date = due_date

    db.session.commit()
    return jsonify(tradeoff.to_dict())
