import uuid
from sqlalchemy import ForeignKey, DateTime, func, UUID
from sqlalchemy.orm import relationship
from config.Database import Base
from sqlalchemy.orm import Mapped, mapped_column
from typing import TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from model.SmartShareFolders import SmartShareFolder

class SmartShareImagesMetaData(Base):
    __tablename__ = "smart_share_images_metadata"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(nullable=False)
    file_type: Mapped[str] = mapped_column(nullable=False)
    upload_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    image_download_path: Mapped[str] = mapped_column(nullable=False)
    image_download_validity: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    smart_share_folder_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("smart_share_folders.id", ondelete='CASCADE'), nullable=False)
    
    # Relationship to FoldersInS3
    smart_share_folder: Mapped["SmartShareFolder"] = relationship(back_populates="smart_share_images_metadata")
