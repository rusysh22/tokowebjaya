import enum
import secrets
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.core.database import Base


class ApiKeyScope(str, enum.Enum):
    read = "read"           # GET only
    write = "write"         # GET + POST/PUT
    full = "full"           # All endpoints


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    name = Column(String(255), nullable=False)           # e.g. "My App Integration"
    key_hash = Column(String(64), unique=True, nullable=False, index=True)
    key_prefix = Column(String(8), nullable=False)       # first 8 chars, for display

    scope = Column(Enum(ApiKeyScope), default=ApiKeyScope.read, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    last_used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="api_keys")

    @staticmethod
    def generate_key() -> tuple[str, str]:
        """Returns (raw_key, prefix). Store hash of raw_key."""
        raw = "twj_" + secrets.token_urlsafe(32)
        prefix = raw[:8]
        return raw, prefix

    @staticmethod
    def hash_key(raw_key: str) -> str:
        import hashlib
        return hashlib.sha256(raw_key.encode()).hexdigest()
