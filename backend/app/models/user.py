"""
User model for authentication and authorization.
"""

from sqlalchemy import Column, String, Boolean, DateTime

from app.core.database import Base
from app.core.utils import utc_now_naive


class User(Base):
    """User model for persistent authentication."""
    
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(255), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    
    # Workspace association
    default_workspace_id = Column(String(36), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=utc_now_naive, nullable=False)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)
    last_login_at = Column(DateTime, nullable=True)
    
    # API rate limiting
    api_calls_today = Column(String(20), default="0", nullable=False)  # JSON: {"count": 0, "date": "2024-01-01"}
    
    def __repr__(self):
        return f"<User {self.email}>"
