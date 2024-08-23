from datetime import datetime
from sqlalchemy import ForeignKey, DateTime, func, BigInteger
from sqlalchemy.orm import relationship, Mapped, mapped_column
from config.Database import Base
from typing import List, TYPE_CHECKING


if TYPE_CHECKING:
    from model.User import User
    from model.ImagesMetaData import ImagesMetaData

#It trackes all tables created By user in S3 either in culling module or smart share 
class FoldersInS3(Base):
    __tablename__='user_s3_folders'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, nullable=False, autoincrement=True)
    name: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())
    location_in_s3: Mapped[str] = mapped_column(nullable=False)
    total_size: Mapped[int] = mapped_column(default=0)
    module: Mapped[str] = mapped_column(nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Relationship back to User
    created_by: Mapped["User"] = relationship(back_populates="folders")

    # Relationship back to Images Metadata
    images: Mapped[List["ImagesMetaData"]] = relationship(back_populates='folder', cascade="all, delete-orphan")