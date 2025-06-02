from src.config.Database import Base
from sqlalchemy import DateTime, func
from sqlalchemy.orm import relationship
from sqlalchemy.orm import mapped_column, Mapped
from typing import List,TYPE_CHECKING
from datetime import datetime
from sqlalchemy import JSON

if TYPE_CHECKING:
    from src.model.CullingFolders import CullingFolder
    from src.model.SmartShareFolders import SmartShareFolder
    from src.model.EventArrangmentForm import EventArrangmentForm
    from src.model.AssociationTable import SmartShareFoldersSecondaryUsersAssociation


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
    
    # Relationship back to the association table
    smart_share_folder_association:Mapped[List["SmartShareFoldersSecondaryUsersAssociation"]] = relationship(back_populates="user", cascade="all,delete-orphan")


# class SecondaryUser(Base):
#     __tablename__ = "secondary_user"
    
#     user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, nullable=False, default=uuid.uuid4)
#     first_name:Mapped[str] = mapped_column(nullable=False)
#     last_name:Mapped[str] = mapped_column(nullable=False)
#     email:Mapped[str] = mapped_column(nullable=False)
#     phone:Mapped[str] = mapped_column(default=None)
#     # access_at:Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
   
#     # Relationship back to the association table
#     smart_share_folder_association:Mapped[List["SmartShareFoldersSecondaryUsersAssociation"]] = relationship(back_populates="secondary_user", cascade="all,delete-orphan")
   
    