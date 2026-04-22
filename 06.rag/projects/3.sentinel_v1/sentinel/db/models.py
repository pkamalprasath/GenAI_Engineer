"""
SQLAlchemy ORM models — mirrors 001_initial_schema.sql.
All tables carry tenant_id for row-level isolation.
Import Base from here to run `Base.metadata.create_all()` in tests.
"""
from __future__ import annotations

import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class DecisionRecord(Base):
    __tablename__ = "decision_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[str] = mapped_column(String(100), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False)
    outcome: Mapped[str] = mapped_column(String(50), nullable=False)
    decision_timestamp: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(100))
    reasoning_text: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("case_id", "tenant_id"),
        Index("idx_decisions_tenant_date", "tenant_id", "decision_timestamp"),
    )


class ProvenanceNode(Base):
    __tablename__ = "provenance_nodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    node_id: Mapped[str] = mapped_column(String(200), nullable=False)
    node_type: Mapped[str] = mapped_column(String(50), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)

    __table_args__ = (
        UniqueConstraint("node_id", "tenant_id"),
        Index("idx_prov_nodes_tenant", "tenant_id"),
    )


class ProvenanceEdge(Base):
    __tablename__ = "provenance_edges"

    id: Mapped[int] = mapped_column(primary_key=True)
    edge_id: Mapped[str] = mapped_column(String(200), nullable=False)
    source_id: Mapped[str] = mapped_column(String(200), nullable=False)
    target_id: Mapped[str] = mapped_column(String(200), nullable=False)
    relation: Mapped[str] = mapped_column(String(100), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False)
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)

    __table_args__ = (
        UniqueConstraint("edge_id", "tenant_id"),
        Index("idx_prov_edges_tenant", "tenant_id"),
        Index("idx_prov_edges_source", "source_id", "tenant_id"),
    )


class Investigation(Base):
    __tablename__ = "investigations"

    id: Mapped[int] = mapped_column(primary_key=True)
    investigation_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="queued")
    domain: Mapped[str] = mapped_column(String(50), nullable=False)
    trigger_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    state_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    total_cost_usd: Mapped[float] = mapped_column(Numeric(10, 6), default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime)

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','discovering','investigating','analyzing',"
            "'pending_human','reporting','complete','failed')",
            name="chk_status",
        ),
        Index("idx_investigations_tenant", "tenant_id", "created_at"),
    )


class Escalation(Base):
    __tablename__ = "escalations"

    id: Mapped[int] = mapped_column(primary_key=True)
    escalation_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    investigation_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("investigations.investigation_id"), nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    draft_report: Mapped[str | None] = mapped_column(Text)
    human_response: Mapped[str | None] = mapped_column(Text)
    reviewer_id: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    resolved_at: Mapped[datetime.datetime | None] = mapped_column(DateTime)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','resolved','rejected')", name="chk_esc_status"
        ),
        Index("idx_escalations_tenant_status", "tenant_id", "status", "created_at"),
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(200))
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (Index("idx_audit_tenant_time", "tenant_id", "created_at"),)
