from sqlalchemy import ForeignKey, DateTime, func,String, UUID
from sqlalchemy.orm import relationship
from config.Database import Base
from sqlalchemy.orm import Mapped, mapped_column
from typing import TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from model.User import User
    from model.FolderInS3 import FoldersInS3

class ImagesMetaData(Base):
    __tablename__ = "imagesmetadata"
    id: Mapped[str] = mapped_column(primary_key=True, nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)
    file_type: Mapped[str] = mapped_column(nullable=False)
    upload_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    download_path: Mapped[str] = mapped_column(nullable=False)
    detection_status:Mapped[str] = mapped_column(nullable=False)
    link_validity: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    folder_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user_s3_folders.id", ondelete='CASCADE'), nullable=False)
    
    # Relationship back to User
    owner: Mapped["User"] = relationship(back_populates="images")

    # Relationship to FoldersInS3
    folder: Mapped["FoldersInS3"] = relationship(back_populates="images")
