from datetime import datetime
from sqlalchemy import ForeignKey, DateTime, func, UUID, String, Enum as SqlEnum
from sqlalchemy.orm import relationship, Mapped, mapped_column
from src.config.Database import Base
from typing import List, TYPE_CHECKING
import uuid
from enum import Enum

if TYPE_CHECKING:
    from src.model.User import User
    from src.model.SmartShareImagesMetaData import SmartShareImagesMetaData
    from src.model.AssociationTable import SmartShareFoldersSecondaryUsersAssociation

class PublishStatus(Enum):
    PUBLISHED = "Published"
    NOT_PUBLISHED = "Not Published"
    PENDING = "Pending"

def get_enum_values(enum_class):
    return [member.value for member in enum_class]

#It trackes all tables created By user in smart share module
class SmartShareFolder(Base):
    __tablename__ = 'smart_share_folders'

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, nullable=False, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(String(250), nullable=True)
    cover_image:Mapped[str] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    path_in_s3: Mapped[str] = mapped_column(nullable=False)
    total_size: Mapped[int] = mapped_column(default=0)
    status = mapped_column(SqlEnum(PublishStatus, values_callable=get_enum_values, name="publishstatus"), nullable=False, default=PublishStatus.NOT_PUBLISHED.value)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Relationship back to User
    user: Mapped["User"] = relationship(back_populates="smart_share_folders")
    
    # Relationship back to Images Metadata
    smart_share_images_metadata: Mapped[List["SmartShareImagesMetaData"]] = relationship(back_populates='smart_share_folder', cascade="all, delete-orphan")
    
    # Relationship back to the association table
    user_association:Mapped[List["SmartShareFoldersSecondaryUsersAssociation"]] = relationship(back_populates="smart_share_folder", cascade="all,delete-orphan")
    