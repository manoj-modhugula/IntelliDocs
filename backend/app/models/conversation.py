"""
Conversation and ConversationMessage models for persistent chat history.
"""

from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, Text, DateTime, ForeignKey, Index, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.utils import utc_now_naive


class Conversation(Base):
    """Persistent conversation model - stores conversation metadata."""

    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="New Chat")
    workspace_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    pinned_message_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array stored as text

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now_naive, onupdate=utc_now_naive
    )

    # Relationships
    messages: Mapped[List["ConversationMessage"]] = relationship(
        "ConversationMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ConversationMessage.created_at",
    )

    __table_args__ = (
        Index("idx_conversation_user", "user_id"),
        Index("idx_conversation_workspace", "workspace_id"),
        Index("idx_conversation_user_workspace", "user_id", "workspace_id"),
    )


class ConversationMessage(Base):
    """Persistent message model - stores individual chat messages."""

    __tablename__ = "conversation_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # "user" or "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Threading: optional reply-to message ID
    parent_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("conversation_messages.id", ondelete="SET NULL"), nullable=True
    )

    # Citations stored as JSON
    citations: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array stored as text
    follow_up_suggestions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)

    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")
    replies: Mapped[List["ConversationMessage"]] = relationship(
        "ConversationMessage",
        back_populates="parent",
        cascade="all, delete-orphan",
    )
    parent: Mapped[Optional["ConversationMessage"]] = relationship(
        "ConversationMessage",
        back_populates="replies",
        remote_side=[id],
    )

    __table_args__ = (
        Index("idx_message_conversation", "conversation_id"),
        Index("idx_message_created", "created_at"),
        Index("idx_message_parent", "parent_id"),
    )
