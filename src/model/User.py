from datetime import timezone
from config.Database import Base
from sqlalchemy import Column, Boolean, String, ForeignKey, DateTime, func, BigInteger
from sqlalchemy.orm import relationship
from model import ImagesMetaData

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    email_verified = Column(Boolean, nullable=False, default=False)
    picture = Column(String, default=None)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    tokens = relationship("Token", back_populates="user", cascade="all, delete-orphan")
    images = relationship("ImagesMetaData", back_populates="owner", cascade="all, delete-orphan")

class Token(Base):
    __tablename__ = 'tokens'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    access_token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    user_id = Column(String, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    user = relationship("User", back_populates="tokens")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), default=None)
