"""
SQLAlchemy models for MARTI (Material Acquisition, Routing, Triage, Impact).

**The S4 rule**: every table below except the last group is a mocked copy of something S4
actually holds, and each class names its S4 source. MARTI never invents a field S4 couldn't
hand it over an API — no "expected time per operation" beyond the routing's own standard
values, no fudge factors, no made-up promise dates. When S4 doesn't know something (a PO the
supplier hasn't confirmed, a PR nobody has released), MARTI says so rather than guessing.

The one input that isn't S4 is a Component whose material has no S4 master yet — that line
arrives from the engineering BOM before anyone has created the master, which is exactly why
"master missing" is worth showing at all.

**MARTI's own tables** (the last group): ProjectRank (Triage — the stack rank and need-by date
leadership sets), PriorityChange (the log of every re-rank, who and why, and where the idea came
from), HotFlag (expedite requests raised automatically when a project moves up), and Proposal (a
suggested re-rank or capacity change from MARTI's engine, the AI, or a person, waiting on a
human decision). Impact is never stored —
scheduler.py computes it fresh from all of the above on every read.
"""

from datetime import datetime, timezone

from db import _uuid, db

PROCUREMENT_TYPES = ("E", "F", "X")  # MARC-BESKZ: in-house production, external procurement, both
PR_RELEASE_STATUSES = ("not_released", "released")  # EBAN-FRGKZ, collapsed to the one fact that matters
INSPECTION_STATUSES = ("none", "in_qi", "accepted", "rejected")  # QALS usage decision on the GR lot
QUALITY_DESIGNATORS = ("defect", "rework", "mrb_hold", "scrap")  # MARTI's grouping of QMEL codings
FLAG_STATUSES = ("open", "acknowledged", "resolved")
PROPOSAL_SOURCES = ("engine", "ai", "person")  # who suggested it; a person always commits
PROPOSAL_KINDS = ("rerank", "capacity")
PROPOSAL_STATUSES = ("open", "committed", "accepted", "dismissed")


def _now():
    """Naive UTC. Every timestamp MARTI stores or compares is naive UTC."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(value):
    """Dates as YYYY-MM-DD; datetimes as UTC with a Z so the browser shows local time."""
    if not value:
        return None
    return value.isoformat() + "Z" if isinstance(value, datetime) else value.isoformat()


# --- Mocked S4 ---------------------------------------------------------------------------------


class WorkCenter(db.Model):
    """S4: CRHD (work center) + KAKO (available capacity). `capacity_hours_per_day` is the
    capacity header's available hours per working day — the only capacity fact the forecast
    uses."""

    __tablename__ = "work_center"

    code = db.Column(db.String(20), primary_key=True)  # CRHD-ARBPL
    description = db.Column(db.String(120), nullable=False)
    capacity_hours_per_day = db.Column(db.Float, nullable=False, default=8.0)

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "description": self.description,
            "capacity_hours_per_day": self.capacity_hours_per_day,
        }


class MaterialMaster(db.Model):
    """S4: MARA/MARC (+ MARD for stock). A material with no row here has no S4 master."""

    __tablename__ = "material_master"

    material_number = db.Column(db.String(40), primary_key=True)  # MATNR
    description = db.Column(db.String(200), nullable=False)  # MAKTX
    procurement_type = db.Column(db.String(1), nullable=False, default="F")  # MARC-BESKZ
    unit = db.Column(db.String(10), nullable=False, default="EA")  # MARA-MEINS
    # MARD-LABST — unrestricted plant stock, for common items not bought against a project.
    unrestricted_stock = db.Column(db.Float, nullable=False, default=0)

    def to_dict(self) -> dict:
        return {
            "material_number": self.material_number,
            "description": self.description,
            "procurement_type": self.procurement_type,
            "unit": self.unit,
            "unrestricted_stock": self.unrestricted_stock,
        }


class PurchaseRequisition(db.Model):
    """S4: EBAN. `depot_project_id` stands in for the WBS account assignment (EBKN-PS_PSP_PNR)
    — how S4 itself ties a requisition to a project."""

    __tablename__ = "purchase_requisition"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    pr_number = db.Column(db.String(20), nullable=False)  # BANFN
    depot_project_id = db.Column(db.String(36), nullable=False, index=True)
    material_number = db.Column(db.String(40), nullable=False, index=True)
    quantity = db.Column(db.Float, nullable=False)
    release_status = db.Column(db.String(20), nullable=False, default="not_released")
    created_on = db.Column(db.Date, nullable=False)  # BADAT

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "pr_number": self.pr_number,
            "material_number": self.material_number,
            "quantity": self.quantity,
            "release_status": self.release_status,
            "created_on": _iso(self.created_on),
        }


class PurchaseOrder(db.Model):
    """S4: EKKO/EKPO (header/item), EKET (requested delivery date), EKES (supplier
    confirmation), MSEG movement 101 (goods receipt), QALS (the GR inspection lot's usage
    decision). `confirmed_date` is null until the supplier actually confirms — the forecast
    falls back to the requested date and labels it unconfirmed, never invents one."""

    __tablename__ = "purchase_order"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    po_number = db.Column(db.String(20), nullable=False)  # EBELN
    pr_number = db.Column(db.String(20), nullable=True)  # EKPO-BANFN
    depot_project_id = db.Column(db.String(36), nullable=False, index=True)  # WBS account assignment
    material_number = db.Column(db.String(40), nullable=False, index=True)
    supplier = db.Column(db.String(120), nullable=True)  # EKKO-LIFNR (name, for display)
    quantity = db.Column(db.Float, nullable=False)
    created_on = db.Column(db.Date, nullable=False)  # EKKO-BEDAT
    requested_date = db.Column(db.Date, nullable=False)  # EKET-EINDT
    confirmed_date = db.Column(db.Date, nullable=True)  # EKES-EINDT
    gr_date = db.Column(db.Date, nullable=True)  # MSEG-BUDAT, movement 101
    inspection_status = db.Column(db.String(20), nullable=False, default="none")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "po_number": self.po_number,
            "pr_number": self.pr_number,
            "material_number": self.material_number,
            "supplier": self.supplier,
            "quantity": self.quantity,
            "created_on": _iso(self.created_on),
            "requested_date": _iso(self.requested_date),
            "confirmed_date": _iso(self.confirmed_date),
            "gr_date": _iso(self.gr_date),
            "inspection_status": self.inspection_status,
        }


class ProductionOrder(db.Model):
    """S4: AFKO/AFPO. `released_at` (system status REL) is when the order's first operation
    started waiting — its arrival at the first work center."""

    __tablename__ = "production_order"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    order_number = db.Column(db.String(20), nullable=False, unique=True)  # AUFNR
    depot_project_id = db.Column(db.String(36), nullable=False, index=True)  # WBS assignment
    material_number = db.Column(db.String(40), nullable=False)  # what this order makes
    quantity = db.Column(db.Float, nullable=False)  # GAMNG
    released_at = db.Column(db.DateTime, nullable=True)

    operations = db.relationship(
        "Operation", back_populates="order", cascade="all, delete-orphan", lazy="selectin",
        order_by="Operation.seq",
    )
    components = db.relationship(
        "Component", back_populates="order", cascade="all, delete-orphan", lazy="selectin",
    )


class Operation(db.Model):
    """S4: AFVC/AFVV (routing operation + standard values) and AFRU (confirmations).

    Standard values are exactly what the routing holds — setup hours (VGW01) and run hours per
    unit (VGW02 over the base quantity). Actuals are confirmation timestamps and quantities:
    first confirmation start (ISDD/ISDZ), final confirmation finish (IEDD/IEDZ), yield (LMNGA),
    scrap (XMNGA), rework (RMNGA).

    Arrival at the work center is never stored — it's the previous operation's final
    confirmation (or the order's release for the first one). Dwell = now − arrival, wall clock,
    same "no fake precision" stance Dude, Where's My Part? took."""

    __tablename__ = "operation"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    order_id = db.Column(db.String(36), db.ForeignKey("production_order.id"), nullable=False, index=True)
    seq = db.Column(db.Integer, nullable=False)  # VORNR
    description = db.Column(db.String(120), nullable=False)  # LTXA1
    work_center = db.Column(db.String(20), db.ForeignKey("work_center.code"), nullable=False)
    setup_hours = db.Column(db.Float, nullable=False, default=0)  # VGW01
    run_hours_per_unit = db.Column(db.Float, nullable=False, default=0)  # VGW02 / base qty
    started_at = db.Column(db.DateTime, nullable=True)
    finished_at = db.Column(db.DateTime, nullable=True)
    yield_qty = db.Column(db.Float, nullable=False, default=0)
    scrap_qty = db.Column(db.Float, nullable=False, default=0)
    rework_qty = db.Column(db.Float, nullable=False, default=0)

    order = db.relationship("ProductionOrder", back_populates="operations")


class Component(db.Model):
    """S4: RESB — a production order's component reservation, including the operation it's
    allocated to (RESB-VORNR), which is what lets MARTI say *which step* is waiting on material
    rather than just "the order is short something."

    The one exception to the S4 rule: before a master exists, the line comes from the
    engineering BOM, and `material_number` has no MaterialMaster row. That's the "master
    missing" state."""

    __tablename__ = "component"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    order_id = db.Column(db.String(36), db.ForeignKey("production_order.id"), nullable=False, index=True)
    operation_seq = db.Column(db.Integer, nullable=False)  # RESB-VORNR
    material_number = db.Column(db.String(40), nullable=False)  # RESB-MATNR
    description = db.Column(db.String(200), nullable=True)  # from the eBOM when no master yet
    quantity = db.Column(db.Float, nullable=False)  # RESB-BDMNG

    order = db.relationship("ProductionOrder", back_populates="components")


class QualityNotification(db.Model):
    """S4: QMEL (+ QMFE defect items), against a production order operation. `designator` is
    MARTI's grouping of the notification's coding into the four things a manager scans for.
    An open `mrb_hold` stops the operation — the forecast won't move past it."""

    __tablename__ = "quality_notification"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    notification_number = db.Column(db.String(20), nullable=False)  # QMNUM
    order_id = db.Column(db.String(36), db.ForeignKey("production_order.id"), nullable=False, index=True)
    operation_seq = db.Column(db.Integer, nullable=False)
    designator = db.Column(db.String(20), nullable=False)  # see QUALITY_DESIGNATORS
    description = db.Column(db.Text, nullable=False)  # QMTXT
    quantity = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_now)  # QMDAT
    closed_at = db.Column(db.DateTime, nullable=True)  # completion date

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "notification_number": self.notification_number,
            "operation_seq": self.operation_seq,
            "designator": self.designator,
            "description": self.description,
            "quantity": self.quantity,
            "created_at": _iso(self.created_at),
            "closed_at": _iso(self.closed_at),
            "open": self.closed_at is None,
        }


# --- MARTI's own -------------------------------------------------------------------------------


class ProjectRank(db.Model):
    """Triage: one row per manufacturing project — where leadership has ranked it (1 = first
    call on shared work centers) and when the customer needs it. Neither lives in S4."""

    __tablename__ = "project_rank"

    depot_project_id = db.Column(db.String(36), primary_key=True)
    rank = db.Column(db.Integer, nullable=False)
    need_by = db.Column(db.Date, nullable=True)
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now, nullable=False)


class PriorityChange(db.Model):
    """One committed re-rank: who, why, and the order before and after (lists of Depot project
    ids, rank 1 first). The history of Triage decisions, and what every HotFlag traces back
    to."""

    __tablename__ = "priority_change"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    changed_by = db.Column(db.String(120), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    before = db.Column(db.JSON, nullable=False)
    after = db.Column(db.JSON, nullable=False)
    changed_at = db.Column(db.DateTime, default=_now, nullable=False)
    # Where the ranking came from. The person in changed_by always made the commit.
    source = db.Column(db.String(20), nullable=False, default="person")
    proposal_id = db.Column(db.String(36), nullable=True)
    # The Depot persona who committed it (the "viewing as" menu), when known.
    person_id = db.Column(db.String(36), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "changed_by": self.changed_by,
            "reason": self.reason,
            "source": self.source,
            "proposal_id": self.proposal_id,
            "person_id": self.person_id,
            "before": self.before,
            "after": self.after,
            "changed_at": _iso(self.changed_at),
        }


class HotFlag(db.Model):
    """An expedite request on one blocking item — raised by MARTI itself when a PriorityChange
    moves a project up, never hand-raised. The buyer or shop acknowledges it with a typed name
    (same pattern as Dude, Where's My Part?'s hot flags); it's resolved when the blocker clears
    or someone marks it done."""

    __tablename__ = "hot_flag"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    depot_project_id = db.Column(db.String(36), nullable=False, index=True)
    priority_change_id = db.Column(db.String(36), db.ForeignKey("priority_change.id"), nullable=False)
    # "material" (a component's supply) or "operation" (a queued / held step). `target_key` is
    # stable across reads: "<material_number>" or "<order_number>/<seq>".
    target_kind = db.Column(db.String(20), nullable=False)
    target_key = db.Column(db.String(80), nullable=False)
    owner = db.Column(db.String(40), nullable=False)  # "Buyer" or the work center code
    title = db.Column(db.String(200), nullable=False)
    detail = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="open")
    raised_at = db.Column(db.DateTime, default=_now, nullable=False)
    acknowledged_by = db.Column(db.String(120), nullable=True)
    acknowledged_at = db.Column(db.DateTime, nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)

    priority_change = db.relationship("PriorityChange", lazy="joined")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "depot_project_id": self.depot_project_id,
            "target_kind": self.target_kind,
            "target_key": self.target_key,
            "owner": self.owner,
            "title": self.title,
            "detail": self.detail,
            "status": self.status,
            "raised_at": _iso(self.raised_at),
            "acknowledged_by": self.acknowledged_by,
            "acknowledged_at": _iso(self.acknowledged_at),
            "resolved_at": _iso(self.resolved_at),
            "priority_change": self.priority_change.to_dict() if self.priority_change else None,
        }


class Proposal(db.Model):
    """A suggested re-rank (`ranking`, rank 1 first) or capacity change (`levers`, the same shape
    scheduler.forecast takes), waiting on a person. The impact a proposal shows is never stored
    here. It's recomputed by the forecast every time it's viewed, so a number the AI wrote can't
    leak into the UI. A re-rank proposal becomes `committed` through the Triage commit; a
    capacity proposal becomes `accepted`, a recorded decision, since the real capacity change
    happens in S4."""

    __tablename__ = "proposal"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    kind = db.Column(db.String(20), nullable=False)  # see PROPOSAL_KINDS
    source = db.Column(db.String(20), nullable=False)  # see PROPOSAL_SOURCES
    title = db.Column(db.String(200), nullable=False)
    rationale = db.Column(db.Text, nullable=True)
    ranking = db.Column(db.JSON, nullable=True)
    levers = db.Column(db.JSON, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="open")
    created_by = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=_now, nullable=False)
    decided_by = db.Column(db.String(120), nullable=True)
    decided_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "source": self.source,
            "title": self.title,
            "rationale": self.rationale,
            "ranking": self.ranking,
            "levers": self.levers,
            "status": self.status,
            "created_by": self.created_by,
            "created_at": _iso(self.created_at),
            "decided_by": self.decided_by,
            "decided_at": _iso(self.decided_at),
        }
