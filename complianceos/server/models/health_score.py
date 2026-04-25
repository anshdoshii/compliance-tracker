import uuid

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base, JsonB


class HealthScore(Base):
    __tablename__ = "health_scores"
    __table_args__ = (
        CheckConstraint("score BETWEEN 0 AND 100", name="health_scores_score_check"),
        Index("idx_health_scores_client", "client_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("smb_profiles.id"), nullable=False
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    breakdown: Mapped[dict | None] = mapped_column(JsonB)
    calculated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    client: Mapped["SMBProfile"] = relationship(back_populates="health_scores")  # noqa: F821
