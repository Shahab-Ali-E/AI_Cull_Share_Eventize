import uuid
from sqlalchemy import ForeignKey, DateTime, func, UUID
from sqlalchemy.orm import relationship
from config.Database import Base
from sqlalchemy.orm import Mapped, mapped_column
from typing import TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from model.CullingFolders import CullingFolder

class ImagesMetaData(Base):
    __tablename__ = "culling_images_metadata"
    id: Mapped[str] = mapped_column(primary_key=True, nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)
    file_type: Mapped[str] = mapped_column(nullable=False)
    upload_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    image_download_path: Mapped[str] = mapped_column(nullable=False)
    image_download_validity: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    culling_folder_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("culling_folders.id", ondelete='CASCADE'), nullable=False)
    detection_status:Mapped[str] = mapped_column(nullable=False)
    
    # Relationship to FoldersInS3
    culling_folder: Mapped["CullingFolder"] = relationship(back_populates="images_metadata")


class TemporaryImageURL(Base):
    __tablename__ = "temporary_culling_image_urls_metadata"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(nullable=False)
    file_type: Mapped[str] = mapped_column(nullable=False)
    image_download_path: Mapped[str] = mapped_column(nullable=False)
    image_download_validity: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True, server_default=func.now())
    culling_folder_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("culling_folders.id", ondelete="CASCADE"), nullable=False)

    # Relationship to CullingFolder
    culling_folder: Mapped["CullingFolder"] = relationship(back_populates="temporary_images_urls")
