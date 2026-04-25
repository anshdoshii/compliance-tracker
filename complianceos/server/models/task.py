import uuid

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("assigned_to IN ('ca','client')", name="tasks_assigned_to_check"),
        CheckConstraint(
            "status IN ('pending','in_progress','waiting_on_client','done','cancelled')",
            name="tasks_status_check",
        ),
        CheckConstraint("created_by IN ('ca','client','system')", name="tasks_created_by_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )
    ca_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ca_profiles.id", ondelete="CASCADE"), nullable=False
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("smb_profiles.id", ondelete="CASCADE"), nullable=False
    )
    compliance_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("client_compliance_items.id")
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    assigned_to: Mapped[str | None] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(server_default="pending")
    due_date: Mapped[DateTime | None] = mapped_column(DateTime(timezone=False))
    completed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str | None] = mapped_column(String(10))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    ca: Mapped["CAProfile"] = relationship(back_populates="tasks")  # noqa: F821
    client: Mapped["SMBProfile"] = relationship(back_populates="tasks")  # noqa: F821
    compliance_item: Mapped["ClientComplianceItem"] = relationship(back_populates="tasks")  # noqa: F821
    documents: Mapped[list["Document"]] = relationship(back_populates="task")  # noqa: F821
    messages: Mapped[list["Message"]] = relationship(back_populates="linked_task")  # noqa: F821
