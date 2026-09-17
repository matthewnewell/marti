"""
MARTI's Agent tab — an ongoing conversation about one manufacturing project, grounded in its
materials, acquisition orders, routing status, and Tension/Impact. Same shape as Value Stream's
own routes/ai.py: the frontend owns conversation history, this route rebuilds the project's
context fresh on every call so a Tension edit made mid-conversation is reflected immediately.
"""

from flask import Blueprint, jsonify, request

import ai_client
import depot_client
from models import Material, Tension

bp = Blueprint("ai", __name__, url_prefix="/api/projects")


def _build_context_lines(depot_project_id: str, project_name: str) -> list[str]:
    materials = Material.query.filter_by(depot_project_id=depot_project_id).all()
    tension = Tension.query.filter_by(depot_project_id=depot_project_id).first()

    lines = [f'Project: "{project_name}"']

    if tension:
        impact = tension.impact()
        lines.append(
            f"Tension (priority): {tension.priority}"
            + (f", due {tension.due_date.isoformat()}" if tension.due_date else ", no due date set")
        )
        lines.append(f"Impact: {impact['reason']}")
    else:
        lines.append("Tension (priority): not set yet.")

    if not materials:
        lines.append("No materials on file for this project yet.")
    for m in materials:
        lines.append(
            f'\nMaterial {m.material_number} ({m.description or "no description"}) — '
            f"procurement type {m.procurement_type}:"
        )
        for a in m.acquisition_orders:
            lines.append(
                f"  - Acquisition order {a.order_number}: {a.status}"
                + (f", need date {a.need_date.isoformat()}" if a.need_date else "")
                + (f", promised {a.promise_date.isoformat()}" if a.promise_date else "")
            )
        for r in m.routings:
            lines.append(
                f"  - Routing op {r.operation_seq} ({r.operation_name}"
                + (f" @ {r.work_center}" if r.work_center else "")
                + f"): {r.status}"
            )

    return lines


_SYSTEM = (
    "You help a program/functional manager track material acquisition, manufacturing "
    "routings, and priority (Tension) for one project. Ground every answer in the specific "
    "materials, orders, routing operations, and Tension/Impact data given below — never give "
    "generic supply-chain advice unconnected to this project. If asked about something the "
    "data can't answer, say so plainly rather than guessing."
)


@bp.post("/<depot_project_id>/chat")
def chat_about_project(depot_project_id):
    if not ai_client.is_configured():
        return jsonify({"error": ai_client.NOT_CONFIGURED_MESSAGE}), 200

    body = request.get_json(force=True) or {}
    messages = body.get("messages")
    if not messages or not isinstance(messages, list):
        return jsonify({"error": "messages (a non-empty list) is required"}), 400

    project = depot_client.fetch_project(depot_project_id)
    if project is None:
        return jsonify({"error": "project not found on the Depot, or the Depot is unreachable"}), 200

    lines = _build_context_lines(depot_project_id, project["name"])
    system = _SYSTEM + "\n\n" + "\n".join(lines)

    reply = ai_client.chat(messages=messages, system=system, max_tokens=1024)
    return jsonify({"reply": reply})
