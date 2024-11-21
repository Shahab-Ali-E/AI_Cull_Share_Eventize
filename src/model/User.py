from config.Database import Base
from sqlalchemy import ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from sqlalchemy.orm import mapped_column, Mapped
from typing import List,TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from model.FolderInS3 import FoldersInS3
    from model.ImagesMetaData import ImagesMetaData
   
class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)
    email_verified: Mapped[bool] = mapped_column(nullable=False, default=False)
    picture: Mapped[str] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    total_culling_storage_used: Mapped[float] = mapped_column(default=0.0)
    total_image_share_storage_used: Mapped[float] = mapped_column(default=0.0)

    # Relationships with user
    tokens: Mapped[List["Token"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    images: Mapped[List["ImagesMetaData"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    folders: Mapped[List["FoldersInS3"]] = relationship(back_populates="created_by", cascade="all, delete-orphan")
   

class Token(Base):
    __tablename__ = 'tokens'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    access_token: Mapped[str] = mapped_column(nullable=False)
    refresh_token: Mapped[str] = mapped_column(nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False)

    #relationship with user
    user: Mapped["User"] = relationship(back_populates="tokens")
