"""
Skill model for chat slash-commands (e.g. /short) that inject LLM instructions.
"""

from datetime import datetime

from sqlalchemy import String, Text, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.utils import utc_now_naive


class Skill(Base):
    """User-defined skill: name (slug for /name) and action (LLM instruction)."""

    __tablename__ = "skills"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)  # slug, e.g. "short"
    action: Mapped[str] = mapped_column(Text, nullable=False)  # instruction for LLM
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now_naive, onupdate=utc_now_naive
    )

    __table_args__ = (
        Index("idx_skill_user_name", "user_id", "name", unique=True),
    )
