from sqlalchemy import Column, Integer, ForeignKey, String, DateTime, func, BigInteger
from sqlalchemy.orm import relationship
from config.Database import Base
from model import User, ImagesMetaData


#It trackes all tables created By user in S3 either in culling module or smart share 
class FoldersInS3(Base):
    __tablename__='user_s3_folders'

    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True)
    name = Column(String(200), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    location_in_s3 = Column(String, nullable=False)
    total_size = Column(BigInteger, default=0)
    module = Column(String, nullable=False)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Relationship back to User
    created_by = relationship("User", back_populates="folders")

    #Relationsip back to Images Metadata
    images = relationship('ImagesMetaData', back_populates='folder', cascade="all, delete-orphan")