"""
MARTI's Agent tab: an ongoing conversation about one manufacturing project, grounded in its
material acquisition status, routing position, quality notifications, Triage rank, and Impact
forecast. Same shape as Value Stream's own routes/ai.py: the frontend owns conversation history,
this route rebuilds the project's context fresh on every call so a re-rank made mid-conversation
is reflected immediately.
"""

from flask import Blueprint, jsonify, request

import ai_client
import service

bp = Blueprint("ai", __name__, url_prefix="/api/projects")


def _hours_to_days(h):
    return f"{round(h / 24, 1)} days" if h is not None else "unknown"


def _build_context_lines(pid: str, ctx) -> list[str]:
    d = service.project_detail(pid, ctx)
    fc = d["forecast"]
    lines = [f'Project: "{d["name"]}" (as of {ctx["forecast"]["as_of"]})']
    ranking = [f"#{i} {ctx['names'].get(p) or p}" for i, p in enumerate(ctx["ranking"], start=1)]
    lines.append("Triage ranking (1 = first call on shared work centers): " + ", ".join(ranking))
    lines.append(
        f"Impact: rank #{fc['rank']}, need-by {fc['need_by'] or 'not set'}, forecast finish "
        f"{fc['projected_finish'] or 'cannot be forecast'}, slack {fc['slack_days']} days, status {fc['status']}."
    )
    if fc.get("blocker"):
        lines.append(f"Forecast blocked by: {fc['blocker']['reason']}")
    for drv in fc.get("drivers", []):
        what = f"waiting for capacity at {drv['key']}" if drv["kind"] == "capacity" else f"waiting for material {drv['key']}"
        lines.append(f"Delay driver: {drv['days']} working days {what}.")
    lines.append("Forecast basis: S4 routing standard hours and work-center capacity, Mon-Fri; "
                 "higher-ranked projects load shared work centers first.")

    lines.append("\nMaterial acquisition:")
    for m in d["acquisition"]:
        lines.append(
            f"  - {m['material_number']} {m['description'] or ''} x{m['quantity']:g} for "
            f"{m['order_number']} op {m['operation_seq']}: {m['stage_label']}"
            + (f" ({m['ref']})" if m["ref"] else "")
            + (f", needed {m['need_date']}" if m["need_date"] else "")
            + (f", ready {m['ready_date']}" if m["ready_date"] else ", no date from S4")
            + (f", {m['late_days']} working days late" if m["late_days"] else "")
            + (" (already consumed)" if m["consumed"] else "")
        )

    lines.append("\nRouting:")
    for o in d["orders"]:
        lines.append(f"  Order {o['order_number']} ({o['description']}, qty {o['quantity']:g}): "
                     f"{o['clear_to_build']['reason']}")
        for op in o["operations"]:
            f = op["forecast"]
            lines.append(
                f"    op {op['seq']} {op['description']} @ {op['work_center']}: {op['state']}"
                + (f", dwell {_hours_to_days(op['dwell_hours'])}" if op["state"] != "not_arrived" else "")
                + (f", forecast {f['start_date']}–{f['finish_date']}" if f.get("start_date") else "")
                + "".join(f"; QN {q['notification_number']} {q['designator']} ({'open' if q['open'] else 'closed'}): {q['description']}"
                          for q in op["quality"])
            )

    if d["hot_flags"]:
        lines.append("\nHot flags:")
        for h in d["hot_flags"]:
            lines.append(f"  - [{h['status']}] {h['title']}: {h['detail']}")
    return lines


_SYSTEM = (
    "You help a program or functional manager understand one manufacturing project: material "
    "acquisition (S4 master, PR, PO, receipt), where each production order is in its routing "
    "(dwell time, quality notifications, what's waiting on material), where leadership has "
    "ranked it in Triage, and the Impact forecast against its need-by date. Ground every "
    "answer in the data below. Never give generic supply-chain advice. The forecast uses S4 "
    "standard hours, which are imperfect for small-lot work, so say so when a conclusion hinges "
    "on it. You cannot change any data: if asked to re-rank, change a date, or acknowledge a "
    "flag, explain where in MARTI to do it rather than claiming you did."
)


@bp.post("/<depot_project_id>/chat")
def chat_about_project(depot_project_id):
    if not ai_client.is_configured():
        return jsonify({"error": ai_client.NOT_CONFIGURED_MESSAGE}), 200

    body = request.get_json(force=True) or {}
    messages = body.get("messages")
    if not messages or not isinstance(messages, list):
        return jsonify({"error": "messages (a non-empty list) is required"}), 400

    ctx = service.context()
    if depot_project_id not in ctx["names"]:
        return jsonify({"error": "not a manufacturing project MARTI knows about"}), 200

    system = _SYSTEM + "\n\n" + "\n".join(_build_context_lines(depot_project_id, ctx))
    reply = ai_client.chat(messages=messages, system=system, max_tokens=1024)
    return jsonify({"reply": reply})
