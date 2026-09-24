"""
AI suggestions for Triage and Constraints. **A stub for now.** The endpoints and the request and
response shapes are final, so the UI is built against them, but nothing calls a model yet.

How it will work once connected (the "AI proposes, the forecast verifies, a person commits" rule,
the same one the ecosystem's Agent tabs follow: an AI must never claim it changed data):
1. Leadership types goals in plain language ("Radar is contractual and can't slip").
2. The model turns them into rules for advisor.best_rankings (`must_on_time`, `fixed`) or into
   candidate capacity levers. It never does scheduling arithmetic itself.
3. MARTI runs the search or scenario through scheduler.forecast.
4. The model writes the rationale from the forecast's own numbers, and the result is saved as a
   Proposal (source "ai"), which shows up in Triage / Constraints with its impact recomputed on
   every view.
5. A person previews and commits (re-rank) or accepts (capacity). The AI can't commit anything.
"""

from flask import Blueprint, jsonify, request

bp = Blueprint("advisor_ai", __name__, url_prefix="/api/ai")

_NOT_CONNECTED = (
    "AI suggestions aren't connected yet. The suggestions shown come from MARTI's own forecast "
    "engine. Once connected, the AI will turn your goals into rules for that same engine and "
    "explain the result; you'll still preview and commit every change yourself."
)


def _stub(kind: str):
    body = request.get_json(force=True, silent=True) or {}
    return jsonify({
        "status": "not_connected",
        "message": _NOT_CONNECTED,
        "kind": kind,
        "goals": (body.get("goals") or "").strip(),
        "proposals": [],
    })


@bp.post("/triage-suggestions")
def triage_suggestions():
    """Request: {goals: str}. Response: {status, message, proposals: [Proposal]}."""
    return _stub("rerank")


@bp.post("/constraint-suggestions")
def constraint_suggestions():
    """Request: {goals: str}. Response: {status, message, proposals: [Proposal]}."""
    return _stub("capacity")
