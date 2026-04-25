import uuid

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base, JsonB, TextArray


class ComplianceItem(Base):
    """Master catalogue of compliance requirements."""

    __tablename__ = "compliance_items"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    compliance_type: Mapped[str] = mapped_column(String(50), nullable=False)
    authority: Mapped[str | None] = mapped_column(String(100))
    frequency: Mapped[str | None] = mapped_column(String(20))
    due_day: Mapped[int | None] = mapped_column(Integer)
    due_day_rule: Mapped[str | None] = mapped_column(String(255))
    applicable_conditions: Mapped[dict | None] = mapped_column(JsonB)
    penalty_per_day: Mapped[int | None] = mapped_column(Integer)
    max_penalty: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    document_checklist: Mapped[list[str] | None] = mapped_column(TextArray)
    ca_action_required: Mapped[bool] = mapped_column(Boolean, server_default="true")
    client_action_required: Mapped[list[str] | None] = mapped_column(TextArray)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    client_items: Mapped[list["ClientComplianceItem"]] = relationship(back_populates="compliance_item")  # noqa: F821


class ClientComplianceItem(Base):
    """Per-client compliance tracking instance."""

    __tablename__ = "client_compliance_items"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','in_progress','waiting_on_client','filed','not_applicable','overdue')",
            name="client_compliance_items_status_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("smb_profiles.id", ondelete="CASCADE"), nullable=False
    )
    ca_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ca_profiles.id")
    )
    compliance_item_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("compliance_items.id"), nullable=False
    )
    financial_year: Mapped[str] = mapped_column(String(10), nullable=False)
    period: Mapped[str | None] = mapped_column(String(20))
    due_date: Mapped[DateTime] = mapped_column(DateTime(timezone=False), nullable=False)
    status: Mapped[str] = mapped_column(server_default="pending")
    completed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    client: Mapped["SMBProfile"] = relationship(back_populates="compliance_items")  # noqa: F821
    compliance_item: Mapped["ComplianceItem"] = relationship(back_populates="client_items")
    tasks: Mapped[list["Task"]] = relationship(back_populates="compliance_item")  # noqa: F821
    documents: Mapped[list["Document"]] = relationship(back_populates="compliance_item")  # noqa: F821
