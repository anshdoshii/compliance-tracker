import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base, TextArray


class Regulation(Base):
    """Scraped government notifications classified by type/sector. Populated by regulation_scraper_job."""

    __tablename__ = "regulations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )
    source_url: Mapped[str | None] = mapped_column(String(500))
    title: Mapped[str | None] = mapped_column(String(500))
    raw_content: Mapped[str | None] = mapped_column(Text)
    compliance_type: Mapped[str | None] = mapped_column(String(50))
    sectors_affected: Mapped[list[str] | None] = mapped_column(TextArray)
    states_affected: Mapped[list[str] | None] = mapped_column(TextArray)
    company_types_affected: Mapped[list[str] | None] = mapped_column(TextArray)
    action_required_by: Mapped[date | None] = mapped_column(Date())
    plain_english_summary: Mapped[str | None] = mapped_column(Text)
    ca_summary: Mapped[str | None] = mapped_column(Text)
    is_classified: Mapped[bool] = mapped_column(Boolean, server_default="false")
    scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
