from config.Database import Base
from sqlalchemy import ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from sqlalchemy.orm import mapped_column, Mapped
from typing import List,TYPE_CHECKING
from datetime import datetime
from sqlalchemy import JSON

if TYPE_CHECKING:
    from model.CullingFolders import CullingFolder
    from model.SmartShareFolders import SmartShareFolder
    from model.EventArrangmentForm import EventArrangmentForm


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(primary_key=True, index=True)
    username:Mapped[str] = mapped_column(nullable=True)
    first_name:Mapped[str] = mapped_column(nullable=True)
    last_name:Mapped[str] = mapped_column(nullable=True)
    profile_image_url: Mapped[str] = mapped_column(default=None)
    email: Mapped[str] = mapped_column(unique=True, index=True, nullable=False)
    email_verified: Mapped[bool] = mapped_column(nullable=False, default=False)
    phone_numbers:Mapped[List[str]] = mapped_column(JSON, nullable=True)
    session_created_at:Mapped[datetime]  = mapped_column(DateTime(timezone=True), server_default=func.now())
    session_last_active_at:Mapped[datetime]  = mapped_column(DateTime(timezone=True), server_default=func.now())
    total_culling_storage_used: Mapped[float] = mapped_column(default=0.0)
    total_image_share_storage_used: Mapped[float] = mapped_column(default=0.0)

    # Relationships with user
    culling_folders: Mapped[List["CullingFolder"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    smart_share_folders: Mapped[List["SmartShareFolder"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    event_arrangment_form: Mapped[List["EventArrangmentForm"]] = relationship(back_populates="user", cascade="all, delete-orphan")
   
    