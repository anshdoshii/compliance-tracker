import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class CAProfile(Base):
    __tablename__ = "ca_profiles"
    __table_args__ = (
        CheckConstraint("plan IN ('starter','growth','pro','firm')", name="ca_profiles_plan_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    icai_number: Mapped[str | None] = mapped_column(String(20), unique=True)
    firm_name: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(100))
    gstin: Mapped[str | None] = mapped_column(String(15))
    plan: Mapped[str] = mapped_column(String(20), server_default="starter")
    plan_client_limit: Mapped[int] = mapped_column(Integer, server_default="10")
    plan_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    razorpay_subscription_id: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="ca_profile")  # noqa: F821
    client_links: Mapped[list["CAClientLink"]] = relationship(back_populates="ca")  # noqa: F821
    tasks: Mapped[list["Task"]] = relationship(back_populates="ca")  # noqa: F821
    messages: Mapped[list["Message"]] = relationship(back_populates="ca")  # noqa: F821
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="ca")  # noqa: F821
