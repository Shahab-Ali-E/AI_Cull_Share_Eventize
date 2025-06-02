from sqlalchemy import Float, ForeignKey, DateTime, Integer, Text, func,String, UUID
from sqlalchemy.orm import relationship
from src.config.Database import Base
from sqlalchemy.orm import Mapped, mapped_column
from typing import TYPE_CHECKING, Optional
from datetime import datetime
import uuid

if TYPE_CHECKING:
    from src.model.User import User

class EventArrangmentForm(Base):
    __tablename__ = "event_arrangment_form"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, nullable=False, default=uuid.uuid4)

    # Personal Information
    fullName: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)

    # Event Information
    eventType: Mapped[str] = mapped_column(String(100), nullable=False)
    eventDescription: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    eventDate: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    numberOfGuests: Mapped[int] = mapped_column(Integer, nullable=False)
    budget: Mapped[float] = mapped_column(Float, nullable=False)

    # Destination Details
    selectCountry: Mapped[str] = mapped_column(String(100), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    alternativeCity: Mapped[str] = mapped_column(String(100), nullable=True)

    # Additional Information
    portfolio: Mapped[str] = mapped_column(String(100), nullable=True)
    specialRequirements: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    submittedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=True)

    # user id
    userId:Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    
    # Relationship back to User
    user: Mapped["User"] = relationship(back_populates="event_arrangment_form")