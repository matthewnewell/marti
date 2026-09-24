"""
MARTI's own suggestions: the arithmetic half of "AI proposes, the forecast verifies, a person
commits". Everything here is deterministic and runs through scheduler.forecast, so every number a
suggestion shows is a forecast result, never an estimate.

- `compare` is the one way any two forecasts are compared (Triage's preview, proposals, capacity
  scenarios all use it).
- `cut_in` answers leadership's "could this small job go first?" for every project: move it to #1
  and see what it gains, what everyone else loses, and whether anyone goes late.
- `best_rankings` searches orderings for fewer late projects and fewer late days, preferring the
  smallest change from the current ranking. It takes `must_on_time` and `fixed` rules, which is
  the hook the AI will use later: the AI turns leadership's plain-language goals into those
  rules and explains the result, and this does the search.
"""

from datetime import date
from itertools import permutations

import scheduler

EXHAUSTIVE_MAX = 7  # 7! = 5040 forecasts; above that, pairwise-swap hill climbing


def compare(ranking: list[str], current: dict, proposed: dict, names: dict) -> list[dict]:
    """Per project: current vs. proposed forecast, finish delta (calendar days, + = later) and
    rank delta (+ = moved up)."""
    out = []
    for pid in ranking:
        p, c = proposed["projects"][pid], current["projects"][pid]
        delta = None
        if p["projected_finish"] and c["projected_finish"]:
            delta = (date.fromisoformat(p["projected_finish"]) - date.fromisoformat(c["projected_finish"])).days
        out.append({
            "depot_project_id": pid,
            "name": names.get(pid),
            "current": c,
            "proposed": p,
            "finish_delta_days": delta,
            "rank_delta": c["rank"] - p["rank"],
        })
    return out


def summarize(rows: list[dict]) -> dict:
    """The headline of a comparison: who goes late, who recovers, total late days before/after."""
    def late_days(f):
        return -f["slack_days"] if f["status"] == "late" and f["slack_days"] is not None else 0

    return {
        "newly_late": [r["depot_project_id"] for r in rows
                       if r["proposed"]["status"] == "late" and r["current"]["status"] != "late"],
        "recovered": [r["depot_project_id"] for r in rows
                      if r["current"]["status"] == "late" and r["proposed"]["status"] != "late"],
        "late_days_before": sum(late_days(r["current"]) for r in rows),
        "late_days_after": sum(late_days(r["proposed"]) for r in rows),
    }


def _score(fc: dict, ids: list[str]) -> tuple[int, int]:
    late = [fc["projects"][p] for p in ids if fc["projects"][p]["status"] == "late"]
    return len(late), sum(-p["slack_days"] for p in late)


def _moves(a: list[str], b: list[str]) -> int:
    """How many pairs changed order between two rankings (Kendall tau distance)."""
    pos = {p: i for i, p in enumerate(b)}
    return sum(1 for i in range(len(a)) for j in range(i + 1, len(a)) if pos[a[i]] > pos[a[j]])


def cut_in(ctx) -> list[dict]:
    """For each project not already #1: what moving it to the top gains it and costs others."""
    ranking = ctx["ranking"]
    out = []
    for pid in ranking[1:]:
        trial = [pid] + [p for p in ranking if p != pid]
        fc = scheduler.forecast(ctx["snap"], trial, ctx["need_by"], ctx["today"], ctx["now"])
        rows = compare(trial, ctx["forecast"], fc, ctx["names"])
        me = next(r for r in rows if r["depot_project_id"] == pid)
        others = [r for r in rows if r["depot_project_id"] != pid]
        gain = -(me["finish_delta_days"] or 0)
        cost = sum(max(r["finish_delta_days"] or 0, 0) for r in others)
        summ = summarize(rows)
        newly_late = [p for p in summ["newly_late"] if p != pid]
        out.append({
            "depot_project_id": pid,
            "name": ctx["names"].get(pid),
            "current_rank": ranking.index(pid) + 1,
            "gain_days": gain,
            "cost_days": cost,
            "newly_late": newly_late,
            "forecastable": me["proposed"]["projected_finish"] is not None,
            # Cheap to expedite: it gains real time and nobody else goes late for it.
            "cheap": gain > 0 and not newly_late,
            "ranking": trial,
        })
    return out


def best_rankings(ctx, must_on_time=(), fixed: dict | None = None, limit: int = 3) -> list[dict]:
    """Rankings that beat the current one: fewer late projects, then fewer late days, then the
    fewest pairwise moves from today's ranking. `fixed` pins {project id: rank}."""
    ranking, fixed = ctx["ranking"], fixed or {}

    def valid(order):
        if any(order.index(p) + 1 != r for p, r in fixed.items() if p in order):
            return False
        return True

    def evaluate(order):
        fc = scheduler.forecast(ctx["snap"], list(order), ctx["need_by"], ctx["today"], ctx["now"])
        if any(fc["projects"][p]["status"] == "late" for p in must_on_time if p in fc["projects"]):
            return None
        return (*_score(fc, ranking), _moves(list(order), ranking)), fc

    candidates = []
    if len(ranking) <= EXHAUSTIVE_MAX:
        for order in permutations(ranking):
            if not valid(order):
                continue
            ev = evaluate(order)
            if ev:
                candidates.append((ev[0], list(order), ev[1]))
    else:
        order, ev = list(ranking), evaluate(ranking)
        best = ev[0] if ev else (10**9, 10**9, 0)
        improved = True
        while improved:
            improved = False
            for i in range(len(order)):
                for j in range(i + 1, len(order)):
                    trial = order[:]
                    trial[i], trial[j] = trial[j], trial[i]
                    if not valid(trial):
                        continue
                    ev = evaluate(trial)
                    if ev and ev[0] < best:
                        best, order, improved = ev[0], trial, True
                        candidates.append((ev[0], trial, ev[1]))

    current_score = (*_score(ctx["forecast"], ranking), 0)
    better = sorted((c for c in candidates if c[0][:2] < current_score[:2]), key=lambda c: c[0])
    out = []
    for score, order, fc in better[:limit]:
        rows = compare(order, ctx["forecast"], fc, ctx["names"])
        summ = summarize(rows)
        out.append({
            "source": "engine",
            "kind": "rerank",
            "title": _title(order, ranking, ctx["names"]),
            "rationale": (f"{score[0]} late project{'s' if score[0] != 1 else ''} "
                          f"({summ['late_days_after']} late days) instead of {current_score[0]} "
                          f"({summ['late_days_before']} late days), with {score[2]} pairwise "
                          f"move{'s' if score[2] != 1 else ''} from today's ranking."),
            "ranking": order,
            "impact": rows,
            "summary": summ,
        })
    return out


def _title(order: list[str], current: list[str], names: dict) -> str:
    """Every project that moves up, biggest move first: "Nacelle Fairing Retrofit ▲3 · Bracket ▲1"."""
    ups = sorted((p for p in order if order.index(p) < current.index(p)),
                 key=lambda p: order.index(p) - current.index(p))
    if not ups:
        return "Reorder"
    return " · ".join(f"{names.get(p) or 'Project'} ▲{current.index(p) - order.index(p)}" for p in ups)


def headcount_to_clear(wip_hours: float, capacity_per_day: float, days: int = 5, shift_hours: float = 8) -> float:
    """Extra people (at one shift each) a work center would need to clear its whole queue plus
    running work within `days` working days. 0 when current capacity already does it."""
    extra_per_day = max(wip_hours / days - capacity_per_day, 0.0)
    return round(extra_per_day / shift_hours, 1)
