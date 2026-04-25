import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base, JsonB


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','sent','paid','overdue','cancelled')",
            name="invoices_status_check",
        ),
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
    invoice_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    line_items: Mapped[dict] = mapped_column(JsonB, nullable=False)
    subtotal: Mapped[int] = mapped_column(Integer, nullable=False)
    gst_rate: Mapped[int] = mapped_column(Integer, server_default="18")
    gst_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    total_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(server_default="draft")
    due_date: Mapped[date | None] = mapped_column(Date())
    razorpay_payment_link_id: Mapped[str | None] = mapped_column(String(100))
    razorpay_payment_link_url: Mapped[str | None] = mapped_column(String(500))
    pdf_r2_key: Mapped[str | None] = mapped_column(String(500))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    ca: Mapped["CAProfile"] = relationship(back_populates="invoices")  # noqa: F821
    client: Mapped["SMBProfile"] = relationship(back_populates="invoices")  # noqa: F821
    payments: Mapped[list["Payment"]] = relationship(back_populates="invoice")  # noqa: F821
