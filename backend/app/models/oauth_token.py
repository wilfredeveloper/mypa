"""
OAuth token storage database models.
"""

from datetime import datetime, timedelta
from typing import Optional, List
from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from cryptography.fernet import Fernet
import os
import base64

from app.core.database import Base
from app.core.config import settings


class OAuthProvider(str, Enum):
    """OAuth provider enumeration."""
    GOOGLE = "google"
    MICROSOFT = "microsoft"
    # Add more providers as needed


class OAuthService(str, Enum):
    """OAuth service enumeration."""
    CALENDAR = "calendar"
    GMAIL = "gmail"
    DRIVE = "drive"
    # Add more services as needed


class OAuthToken(Base):
    """OAuth token storage with encryption."""

    __tablename__ = "oauth_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    provider = Column(String(50), nullable=False, index=True)  # 'google', 'microsoft', etc.
    service = Column(String(50), nullable=False, index=True)   # 'calendar', 'gmail', etc.

    # Encrypted token data
    access_token_encrypted = Column(Text, nullable=False)
    refresh_token_encrypted = Column(Text, nullable=True)

    # Token metadata
    token_type = Column(String(20), default="Bearer", nullable=False)
    scope = Column(Text, nullable=True)  # Space-separated scopes
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Status fields
    is_active = Column(Boolean, default=True, nullable=False)
    is_revoked = Column(Boolean, default=False, nullable=False)

    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_used = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="oauth_tokens")

    def __repr__(self):
        return f"<OAuthToken(id={self.id}, user_id={self.user_id}, provider={self.provider}, service={self.service})>"

    @staticmethod
    def _get_encryption_key() -> bytes:
        """Get encryption key from settings or environment."""
        key = getattr(settings, 'OAUTH_ENCRYPTION_KEY', None) or os.getenv('OAUTH_ENCRYPTION_KEY')
        if not key:
            # Generate a key for development (should be set in production)
            key = Fernet.generate_key()
            print(f"Warning: Generated temporary encryption key. Set OAUTH_ENCRYPTION_KEY in production.")

        if isinstance(key, str):
            key = key.encode()

        return key

    @staticmethod
    def _encrypt_token(token: str) -> str:
        """Encrypt a token string."""
        if not token:
            return ""

        key = OAuthToken._get_encryption_key()
        f = Fernet(key)
        encrypted = f.encrypt(token.encode())
        return base64.b64encode(encrypted).decode()

    @staticmethod
    def _decrypt_token(encrypted_token: str) -> str:
        """Decrypt a token string."""
        if not encrypted_token:
            return ""

        try:
            key = OAuthToken._get_encryption_key()
            f = Fernet(key)
            encrypted_bytes = base64.b64decode(encrypted_token.encode())
            decrypted = f.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception as e:
            print(f"Error decrypting token: {e}")
            return ""

    @property
    def access_token(self) -> str:
        """Get decrypted access token."""
        return self._decrypt_token(self.access_token_encrypted)

    @access_token.setter
    def access_token(self, value: str):
        """Set encrypted access token."""
        self.access_token_encrypted = self._encrypt_token(value)

    @property
    def refresh_token(self) -> Optional[str]:
        """Get decrypted refresh token."""
        if not self.refresh_token_encrypted:
            return None
        return self._decrypt_token(self.refresh_token_encrypted)

    @refresh_token.setter
    def refresh_token(self, value: Optional[str]):
        """Set encrypted refresh token."""
        if value:
            self.refresh_token_encrypted = self._encrypt_token(value)
        else:
            self.refresh_token_encrypted = None

    @property
    def scopes(self) -> List[str]:
        """Get list of scopes."""
        if not self.scope:
            return []
        return self.scope.split()

    @scopes.setter
    def scopes(self, value: List[str]):
        """Set scopes from list."""
        self.scope = " ".join(value) if value else None

    def is_expired(self) -> bool:
        """Check if token is expired."""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at.replace(tzinfo=None)

    def expires_soon(self, minutes: int = 5) -> bool:
        """Check if token expires within specified minutes."""
        if not self.expires_at:
            return False
        threshold = datetime.utcnow() + timedelta(minutes=minutes)
        return self.expires_at.replace(tzinfo=None) <= threshold

    def update_tokens(self, access_token: str, refresh_token: Optional[str] = None,
                     expires_in: Optional[int] = None, scopes: Optional[List[str]] = None):
        """Update token data."""
        self.access_token = access_token
        if refresh_token:
            self.refresh_token = refresh_token
        if expires_in:
            self.expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        if scopes:
            self.scopes = scopes
        self.updated_at = datetime.utcnow()

    def revoke(self):
        """Mark token as revoked."""
        self.is_revoked = True
        self.is_active = False
        self.updated_at = datetime.utcnow()

    def mark_used(self):
        """Update last used timestamp."""
        self.last_used = datetime.utcnow()

    def has_scope(self, required_scope: str) -> bool:
        """Check if token has required scope."""
        return required_scope in self.scopes

    def has_all_scopes(self, required_scopes: List[str]) -> bool:
        """Check if token has all required scopes."""
        token_scopes = set(self.scopes)
        required_scopes_set = set(required_scopes)
        return required_scopes_set.issubset(token_scopes)