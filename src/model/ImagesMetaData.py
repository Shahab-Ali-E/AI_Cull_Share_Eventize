from sqlalchemy import Column, BigInteger, ForeignKey, String, DateTime, func
from sqlalchemy.orm import relationship
from config.Database import Base
from model import User

class ImagesMetaData(Base):
    __tablename__ = "imagesmetadata"
    id = Column(String(400), primary_key=True, nullable=False)
    name = Column(String(200), nullable=False)
    file_type = Column(String(10), nullable=False)
    upload_at = Column(DateTime, server_default=func.now())
    Bucket_folder = Column(String, nullable=False)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Relationship back to User
    owner = relationship("User", back_populates="images")
