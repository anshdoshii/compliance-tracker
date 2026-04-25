import uuid

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint("sender_role IN ('ca','client')", name="messages_sender_role_check"),
        Index("idx_messages_thread", "ca_id", "client_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )
    ca_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ca_profiles.id"), nullable=False
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("smb_profiles.id"), nullable=False
    )
    sender_role: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    attached_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id")
    )
    linked_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id")
    )
    is_read: Mapped[bool] = mapped_column(Boolean, server_default="false")
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    ca: Mapped["CAProfile"] = relationship(back_populates="messages")  # noqa: F821
    client: Mapped["SMBProfile"] = relationship(back_populates="messages")  # noqa: F821
    attached_document: Mapped["Document"] = relationship(back_populates="messages")  # noqa: F821
    linked_task: Mapped["Task"] = relationship(back_populates="messages")  # noqa: F821
