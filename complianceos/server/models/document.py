import uuid

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("uploaded_by IN ('ca','client')", name="documents_uploaded_by_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("smb_profiles.id", ondelete="CASCADE"), nullable=False
    )
    ca_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ca_profiles.id"))
    task_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id"))
    compliance_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("client_compliance_items.id")
    )
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    r2_key: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    uploaded_by: Mapped[str | None] = mapped_column(String(10))
    document_type: Mapped[str | None] = mapped_column(String(50))
    financial_year: Mapped[str | None] = mapped_column(String(10))
    is_deleted: Mapped[bool] = mapped_column(Boolean, server_default="false")
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    client: Mapped["SMBProfile"] = relationship(back_populates="documents")  # noqa: F821
    task: Mapped["Task"] = relationship(back_populates="documents")  # noqa: F821
    compliance_item: Mapped["ClientComplianceItem"] = relationship(back_populates="documents")  # noqa: F821
    messages: Mapped[list["Message"]] = relationship(back_populates="attached_document")  # noqa: F821
