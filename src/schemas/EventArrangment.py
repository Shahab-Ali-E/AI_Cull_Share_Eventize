from pydantic import BaseModel, EmailStr, Field, UUID4, field_validator
from typing import List, Optional
from datetime import datetime

class BookEventFormSchema(BaseModel):
    # Personal Information
    fullName: str = Field(..., max_length=255, title="Full Name", description="Full name of the user.")
    email: EmailStr = Field(..., title="Email Address", description="Email address of the user.")
    phone: str = Field(..., max_length=15, title="Phone Number", description="Phone number of the user.")
    
    # Event Information
    eventType: str = Field(..., max_length=100, title="Event Type", description="Type of event being planned.")
    eventDescription: Optional[str] = Field(None, title="Event Description", description="Description of the event.")
    eventDate: datetime = Field(..., title="Event Date", description="Date of the event.")
    numberOfGuests: int = Field(..., ge=20, title="Number of Guests", description="Expected number of guests.")
    budget: float = Field(..., ge=10000, title="Budget", description="Budget for the event.")
    
    # Destination Details
    selectCountry: str = Field(..., max_length=100, title="Selected Country", description="Country for the event.")
    city: str = Field(..., max_length=100, title="City", description="City for the event.")
    alternativeCity: Optional[str] = Field(None, max_length=100, title="Alternative City", description="Alternative city for the event.")
    
    # Additional Information
    portfolio: Optional[str] = Field(None, title="Portfolio", description="Portfolio details provided by the user.")
    specialRequirements: Optional[str] = Field(None, title="Special Requirements", description="Any special requirements for the event.")
    
    # User ID (optional, depends on your use case)
    userId: str = Field(..., title="User ID", description="The ID of the user submitting the form.")
    
    @field_validator("phone")
    def validate_phone(cls, value):
        """Ensure phone number contains only digits and has a valid length."""
        if len(value) < 10 or len(value) > 20:
            raise ValueError("Phone number must be between 7 and 15 digits.")
        return value
    
    model_config = {
        "json_schema_extra" :{
            "example": {
                "fullName": "John Doe",
                "email": "johndoe@example.com",
                "phone": "+923121112221",
                "eventType": "Wedding",
                "eventDescription": "A beautiful wedding ceremony and reception.",
                "eventDate": "2024-12-31T18:00:00",
                "numberOfGuests": 150,
                "budget": 20000.00,
                "selectCountry": "Pakistan",
                "city": "Islamabad",
                "alternativeCity": "Lahore",
                "portfolio": "wedding",
                "specialRequirements": "Wheelchair access and vegetarian catering.",
                "userId": "user_2pn6uXJhoILeAubepXAoaluOOO2"
            }
        }
    }
    
class GetEventResponse(BaseModel):
    id: UUID4  # UUID field for the event ID

    # Personal Information
    fullName: str
    email: str
    phone: str

    # Event Information
    eventType: str
    eventDescription: Optional[str] = None
    eventDate: datetime
    numberOfGuests: int
    budget: float

    # Destination Details
    selectCountry: str
    city: str
    alternativeCity: Optional[str] = None

    # Additional Information
    portfolio: Optional[str] = None
    specialRequirements: Optional[str] = None

    # Timestamps
    submittedAt: datetime

class GetMultipleEventsResponse(BaseModel):
    events: List[GetEventResponse]
    total_count:int