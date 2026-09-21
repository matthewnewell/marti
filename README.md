# MARTI

**M**aterial · **A**cquisition · **R**outings · **T**ension · **I**mpact

Manufacturing-side project visibility: mocked S4 material/acquisition/routing status, plus a
priority (Tradeoffs) and a computed risk signal (Impact) layer on top. Meant to eventually
replace Dude, Where's My Part? and Dude, Where's My Order? once validated — not done yet.

## The idea

**Material, Acquisition, Routings** are mocked S4 data (no live S4 integration) — a material
master's procurement type (E = in-house production, F = external procurement, X = both) is the
real S4 field this app leans on, not an invented one.

**Tradeoffs** are a priority per project, set by whoever owns it. **Impact** is never stored — it's
computed fresh from Tradeoff's priority and due date against today, the same "compute, don't
cache" convention Value Stream's own metrics engine uses.

**A project shows up here if either is true**: Conway's Depot says the project
`has_manufacturing`, or it has a material master on file with procurement type E/X. Either is
enough — the hybrid exists because Depot's flag is provisional (nobody's required to set it
yet) and the material signal alone would miss a young project that hasn't had parts released.

**Agent and Journal** live in a shared docked side panel (the same file-drawer tab pattern
Value Stream uses) — Agent is a real, working assistant grounded in the project's own
materials/routing/acquisition/Tradeoff context, proxied through Conway's Depot
(`AI_PROVIDER=depot`, no API key of this app's own). Journal is a native rendering of the
Depot's own shared project journal (not the standalone embed widget, which renders as an
independent floating drawer — incompatible with sharing this panel) — the same feed, entries
posted here show up on Depot's own project page too.

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

Conway's Depot (`:8090`) must be running — MARTI reads its project list directly
(`depot_client.py`) and has no data of its own about which projects exist.

## Tests

```bash
cd backend && .venv/bin/python -m pytest
```
