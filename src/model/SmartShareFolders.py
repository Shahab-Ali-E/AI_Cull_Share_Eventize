from datetime import datetime
from sqlalchemy import ForeignKey, DateTime, func, UUID, String
from sqlalchemy.orm import relationship, Mapped, mapped_column
from config.Database import Base
from typing import List, TYPE_CHECKING
import uuid

if TYPE_CHECKING:
    from model.User import User
    from model.SmartShareImagesMetaData import SmartShareImagesMetaData

#It trackes all tables created By user in culling module
class SmartShareFolder(Base):
    __tablename__ = 'smart_share_folders'

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, nullable=False, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(String(250), nullable=True)
    cover_image:Mapped[str] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    path_in_s3: Mapped[str] = mapped_column(nullable=False)
    total_size: Mapped[int] = mapped_column(default=0)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Relationship back to User
    user: Mapped["User"] = relationship(back_populates="smart_share_folders")
    
    # Relationship back to Images Metadata
    smart_share_images_metadata: Mapped[List["SmartShareImagesMetaData"]] = relationship(back_populates='smart_share_folder', cascade="all, delete-orphan")
    