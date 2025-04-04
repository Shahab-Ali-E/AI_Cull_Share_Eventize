from datetime import datetime
from sqlalchemy import ForeignKey, DateTime, func, UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column
from config.Database import Base
from typing import List, TYPE_CHECKING
import uuid

if TYPE_CHECKING:
    from model.User import User
    from model.CullingImagesMetaData import ImagesMetaData,TemporaryImageURL

#It trackes all tables created By user in culling module
class CullingFolder(Base):
    __tablename__ = 'culling_folders'

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, nullable=False, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    path_in_s3: Mapped[str] = mapped_column(nullable=False)
    total_size: Mapped[int] = mapped_column(default=0)
    culling_done: Mapped[bool] = mapped_column(nullable=False, default=False)
    culling_in_progress: Mapped[bool] = mapped_column(nullable=False, default=False)
    uploading_in_progress: Mapped[bool] = mapped_column(nullable=False, default=False)
    uploading_task_id: Mapped[str] = mapped_column(nullable=True, default=None)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Relationship back to User
    user: Mapped["User"] = relationship(back_populates="culling_folders")
    
    # Relationship back to Images Metadata
    images_metadata: Mapped[List["ImagesMetaData"]] = relationship(back_populates='culling_folder', cascade="all, delete-orphan")
    temporary_images_urls: Mapped[List["TemporaryImageURL"]] = relationship(back_populates="culling_folder", cascade="all, delete-orphan")

