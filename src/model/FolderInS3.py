from datetime import datetime
from sqlalchemy import JSON, ForeignKey, DateTime, func, UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column
from config.Database import Base
from typing import Dict, List, TYPE_CHECKING, Optional
import uuid

if TYPE_CHECKING:
    from model.User import User
    from model.ImagesMetaData import ImagesMetaData

#It trackes all tables created By user in S3 either in culling module or smart share 
class FoldersInS3(Base):
    __tablename__ = 'user_s3_folders'

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, nullable=False, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    location_in_s3: Mapped[str] = mapped_column(nullable=False)
    total_size: Mapped[int] = mapped_column(default=0)
    module: Mapped[str] = mapped_column(nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    culling_done: Mapped[bool] = mapped_column(nullable=False, default=False)
    culling_in_progress: Mapped[bool] = mapped_column(nullable=False, default=False)
    temporary_images_urls: Mapped[Optional[List[Dict[str, Optional[str]]]]] = mapped_column(
        JSON, nullable=True, default=[]
    )
    
    # Relationship back to User
    created_by: Mapped["User"] = relationship(back_populates="folders")

    # Relationship back to Images Metadata
    images: Mapped[List["ImagesMetaData"]] = relationship(back_populates='folder', cascade="all, delete-orphan")
