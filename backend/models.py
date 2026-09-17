"""
SQLAlchemy models for MARTI (Material, Acquisition, Routings, Tension, Impact).

Material / AcquisitionOrder / Routing are mocked S4 data — this app holds no real S4
integration, just a shape approximating it closely enough to prove the idea. `procurement_type`
on Material (E = in-house production, F = external procurement, X = both — the real S4 MRP2
field) is what the hybrid manufacturing-project trigger checks, alongside Conway's Depot's own
`Project.has_manufacturing` flag (see routes/projects.py).

Tension is the one genuinely new structure this app owns: a priority per project, plus the due
date Impact is computed from. Impact itself is never stored — it's derived fresh at read time
from Tension.priority + Tension.due_date vs. today, same "compute, don't cache" convention
Value Stream's own metrics engine already follows.
"""

from datetime import date, datetime, timezone

from db import _uuid, db

PROCUREMENT_TYPES = ("E", "F", "X")  # in-house production, external procurement, both
ACQUISITION_STATUSES = ("open", "released", "received", "on_hold")
ROUTING_STATUSES = ("not_started", "in_process", "complete", "on_hold")
PRIORITIES = ("high", "medium", "low")


def _now():
    return datetime.now(timezone.utc)


class Material(db.Model):
    """One mocked S4 material master row, tied directly to a Conway's Depot project id — MARTI
    isn't Depot-unaware the way Value Stream is; it already reads Depot's own project list via
    depot_client, so there's no crosswalk indirection needed here."""

    __tablename__ = "material"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    depot_project_id = db.Column(db.String(36), nullable=False, index=True)
    material_number = db.Column(db.String(60), nullable=False)
    description = db.Column(db.Text, nullable=True)
    # E or X here is the hybrid trigger's other half — see routes/projects.py's
    # _projects_with_manufacturing.
    procurement_type = db.Column(db.String(1), nullable=False, default="F")
    created_at = db.Column(db.DateTime, default=_now, nullable=False)

    acquisition_orders = db.relationship(
        "AcquisitionOrder", back_populates="material", cascade="all, delete-orphan", lazy="selectin"
    )
    routings = db.relationship(
        "Routing", back_populates="material", cascade="all, delete-orphan", lazy="selectin",
        order_by="Routing.operation_seq",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "depot_project_id": self.depot_project_id,
            "material_number": self.material_number,
            "description": self.description,
            "procurement_type": self.procurement_type,
            "created_at": self.created_at.isoformat(),
            "acquisition_orders": [a.to_dict() for a in self.acquisition_orders],
            "routings": [r.to_dict() for r in self.routings],
        }


class AcquisitionOrder(db.Model):
    """One mocked purchase order / acquisition record against a material — the old Dude,
    Where's My Order? job."""

    __tablename__ = "acquisition_order"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    material_id = db.Column(db.String(36), db.ForeignKey("material.id"), nullable=False, index=True)
    order_number = db.Column(db.String(60), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="open")  # see ACQUISITION_STATUSES
    need_date = db.Column(db.Date, nullable=True)
    promise_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=_now, nullable=False)

    material = db.relationship("Material", back_populates="acquisition_orders")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "material_id": self.material_id,
            "order_number": self.order_number,
            "status": self.status,
            "need_date": self.need_date.isoformat() if self.need_date else None,
            "promise_date": self.promise_date.isoformat() if self.promise_date else None,
            "created_at": self.created_at.isoformat(),
        }


class Routing(db.Model):
    """One mocked manufacturing operation against a material — the old Dude, Where's My Part?
    job."""

    __tablename__ = "routing"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    material_id = db.Column(db.String(36), db.ForeignKey("material.id"), nullable=False, index=True)
    operation_seq = db.Column(db.Integer, nullable=False, default=10)
    operation_name = db.Column(db.String(120), nullable=False)
    work_center = db.Column(db.String(60), nullable=True)
    status = db.Column(db.String(20), nullable=False, default="not_started")  # see ROUTING_STATUSES
    created_at = db.Column(db.DateTime, default=_now, nullable=False)

    material = db.relationship("Material", back_populates="routings")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "material_id": self.material_id,
            "operation_seq": self.operation_seq,
            "operation_name": self.operation_name,
            "work_center": self.work_center,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }


class Tension(db.Model):
    """One priority + due date per project — the one row per project this app actually owns.
    `due_date` lives here, not on Conway's Depot's own Project — it's MARTI's own lens on the
    project (when the org needs it done), not a core fact about the project the way
    has_manufacturing is."""

    __tablename__ = "tension"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    depot_project_id = db.Column(db.String(36), nullable=False, unique=True, index=True)
    priority = db.Column(db.String(10), nullable=False, default="medium")  # see PRIORITIES
    due_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now, nullable=False)

    def impact(self) -> dict:
        """Computed fresh every read, never stored — see the module docstring. Low/medium
        priority plus a due date that's already past or within the next 14 days is flagged;
        high priority is never flagged regardless of date (it's already being treated as
        urgent). No due date at all means impact can't be assessed yet."""
        if self.due_date is None:
            return {"flagged": False, "reason": "No due date on file yet."}
        days_out = (self.due_date - date.today()).days
        if self.priority != "high" and days_out <= 14:
            when = f"{-days_out} days ago" if days_out < 0 else f"in {days_out} days"
            return {
                "flagged": True,
                "reason": f"{self.priority.capitalize()} priority, but due {when}.",
                "days_to_due": days_out,
            }
        return {"flagged": False, "reason": "On track.", "days_to_due": days_out}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "depot_project_id": self.depot_project_id,
            "priority": self.priority,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "impact": self.impact(),
        }
