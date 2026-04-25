import uuid

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class CAClientLink(Base):
    __tablename__ = "ca_client_links"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','active','removed')", name="ca_client_links_status_check"
        ),
        UniqueConstraint("ca_id", "client_id", name="uq_ca_client_links"),
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
    status: Mapped[str] = mapped_column(server_default="pending")
    invited_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    accepted_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    removed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))

    ca: Mapped["CAProfile"] = relationship(back_populates="client_links")  # noqa: F821
    client: Mapped["SMBProfile"] = relationship(back_populates="ca_links")  # noqa: F821
