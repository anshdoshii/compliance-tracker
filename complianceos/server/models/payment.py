import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base, JsonB


class Payment(Base):
    """Tracks Razorpay webhook payment events per invoice. State is always set by webhooks, never by client."""

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('captured','failed','refunded')", name="payments_status_check"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False
    )
    razorpay_payment_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    razorpay_order_id: Mapped[str | None] = mapped_column(String(100))
    # Amount stored in paise (smallest INR unit)
    amount: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str | None] = mapped_column(String(20))
    method: Mapped[str | None] = mapped_column(String(30))
    webhook_payload: Mapped[dict | None] = mapped_column(JsonB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    invoice: Mapped["Invoice"] = relationship(back_populates="payments")  # noqa: F821
