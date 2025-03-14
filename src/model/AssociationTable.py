from datetime import datetime
from config.Database import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import UUID, ForeignKey, DateTime, func
import uuid
from typing import TYPE_CHECKING, List


if TYPE_CHECKING:
    from model.SmartShareFolders import SmartShareFolder
    from model.User import User

class SmartShareFoldersSecondaryUsersAssociation(Base):
    __tablename__ = "smart_share_folders_users_association"
    
    id:Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, nullable=False, default=uuid.uuid4)
    user_id:Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    smart_share_folder_id:Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("smart_share_folders.id", ondelete="CASCADE"), nullable=False)
    accessed_at:Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    
    # relationships
    user:Mapped["User"] = relationship(back_populates="smart_share_folder_association")
    smart_share_folder:Mapped["SmartShareFolder"] = relationship(back_populates="user_association")
    
    
    