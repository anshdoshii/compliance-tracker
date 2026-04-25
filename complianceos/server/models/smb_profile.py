import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base, TextArray


class SMBProfile(Base):
    __tablename__ = "smb_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    company_type: Mapped[str | None] = mapped_column(String(50))
    gstin: Mapped[str | None] = mapped_column(String(15))
    pan: Mapped[str | None] = mapped_column(String(10))
    turnover_range: Mapped[str | None] = mapped_column(String(20))
    employee_count_range: Mapped[str | None] = mapped_column(String(20))
    sectors: Mapped[list[str] | None] = mapped_column(TextArray)
    states: Mapped[list[str] | None] = mapped_column(TextArray)
    gst_registered: Mapped[bool] = mapped_column(Boolean, server_default="false")
    gst_composition: Mapped[bool] = mapped_column(Boolean, server_default="false")
    has_factory: Mapped[bool] = mapped_column(Boolean, server_default="false")
    import_export: Mapped[bool] = mapped_column(Boolean, server_default="false")
    is_listed: Mapped[bool] = mapped_column(Boolean, server_default="false")
    standalone_plan: Mapped[str] = mapped_column(String(20), server_default="free")
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="smb_profile")  # noqa: F821
    ca_links: Mapped[list["CAClientLink"]] = relationship(back_populates="client")  # noqa: F821
    tasks: Mapped[list["Task"]] = relationship(back_populates="client")  # noqa: F821
    documents: Mapped[list["Document"]] = relationship(back_populates="client")  # noqa: F821
    messages: Mapped[list["Message"]] = relationship(back_populates="client")  # noqa: F821
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="client")  # noqa: F821
    health_scores: Mapped[list["HealthScore"]] = relationship(back_populates="client")  # noqa: F821
    compliance_items: Mapped[list["ClientComplianceItem"]] = relationship(back_populates="client")  # noqa: F821
