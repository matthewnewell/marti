# MARTI

**M**aterial **A**cquisition · **R**outing · **T**riage · **I**mpact

Manufacturing-side project visibility for an S4 shop. It replaces Dude, Where's My Part? (routing
and dwell) and Dude, Where's My Order? (procurement status) with one app, and adds the thing
neither had: leadership's priority call and what it costs.

## The idea

The tabs spell the app, left to right. A **project picker** on the right scopes the first two
(and opens the Agent | Journal drawer); leave it on "All projects" for the whole shop.

- **Material & Acquisition**: every component a build needs, from S4 material master (exists or
  not) through PR, PO, supplier confirmation, goods receipt and inspection, dated against when
  the step that consumes it is scheduled to start.
- **Routing**: each project as an assembly tree (top assembly → sub → sub-sub, any depth) with
  rollups, where each order is in its routing, dwell, open rework / MRB holds / scrap, what's
  short on material, and the **critical chain** of orders setting the finish date.
- **Triage & Impact**: leadership's stack rank plus each project's need-by date. This is the only
  data MARTI owns. The Impact forecast loads shared work centers in rank order, so moving one
  project up visibly pushes others out. Re-ranks are previewed before they're committed, and a
  commit raises **hot flags** on whatever is blocking the projects that moved up. Each project
  shows the work it has left (parts, ops, standard hours, hours on the bottleneck), and MARTI
  suggests: better rankings (fewest late projects and late days, smallest change) and a
  **cut-in check** (what each project gains at #1 and what everyone else pays).
- **Constraints**: where queues are building, the people it would take to clear each within a
  week, and a **what-if sandbox** of capacity levers (overtime/extra shift, move labor, new
  equipment, outsource an op) that forecasts every project against them. Scenarios can be saved
  as proposals for leadership to accept or dismiss.

### AI proposes, the forecast verifies, a person commits

Suggestions come from three sources: MARTI's own engine (`advisor.py`), the AI, or a person.
Every suggestion's impact is recomputed by the forecast whenever it's shown, and only a person can
commit a ranking or accept a capacity proposal. The ranking history records "proposed by …,
committed by …". **The AI half is a stub today**: `routes/advisor_ai.py` has the final
endpoints and shapes and answers "not connected". When wired, the model turns leadership's
plain-language goals into rules for the engine's search (`must_on_time`, `fixed`) or candidate
levers, and writes the explanation from the forecast's numbers. It never does scheduling
arithmetic and never commits.

### The S4 rule

Every field except Triage is something S4 can hand over an API, and `models.py` names the S4
table for each. The forecast uses only S4 routing standard hours (setup + run × qty), work-center
available capacity, and PO requested/confirmed dates. There are no efficiency factors and no
invented lead times. When S4 can't date something (a PR with no PO, a missing master, an MRB hold
awaiting disposition), the project is shown as **blocked** instead of getting a guessed date. The
one non-S4 input is an engineering-BOM line whose material has no master yet, which is exactly the
"master missing" state.

S4 data is mocked for now (`backend/demo_data.py`), against the four Conway's Depot demo projects
with a manufacturing side.

## Run it

Backend:

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python app.py          # :8102
```

Frontend:

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0    # :5188
```

Conway's Depot (`:8090`) should be running. MARTI reads project names and the `has_manufacturing`
flag from it (`depot_client.py`) and degrades to ids-only if it's down.

Reload the demo data (resets rankings, history, proposals and hot flags; timestamps become relative to now):

```bash
cd backend && .venv/bin/python refresh_demo.py
```

## Tests

```bash
cd backend && .venv/bin/python -m pytest
```

## Layout

- `backend/models.py`: mocked S4 tables + MARTI's own (ProjectRank, PriorityChange, HotFlag, Proposal)
- `backend/scheduler.py`: the Impact forecast. A pure function of a snapshot, a ranking, today and optional capacity levers
- `backend/advisor.py`: MARTI's own suggestions (ranking search, cut-in check), comparisons, headcount
- `backend/service.py`: shared read views (project rows, order/routing views, acquisition lines, constraints)
- `backend/routes/`: `views` (acquisition, routing), `triage` (board, preview, suggestions, commit, need-by), `constraints` (+ scenario), `proposals`, `hot_flags`, `advisor_ai` (AI suggestions, stub), `summary` (Depot Launchpad tile), `ai` (Agent tab), `projects`
