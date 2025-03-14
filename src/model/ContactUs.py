from datetime import datetime
import uuid
from sqlalchemy import DateTime, Text, func, UUID
from config.Database import Base
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional


class ContactUs(Base):
    __tablename__ = "contact_us"
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, index=True, nullable=False, default=uuid.uuid4)
    first_name:Mapped[str] = mapped_column(nullable=True)
    last_name:Mapped[str] = mapped_column(nullable=True)
    email: Mapped[str] = mapped_column(nullable=False)
    phone:Mapped[Optional[str]] = mapped_column(nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    contact_at:Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=True)


