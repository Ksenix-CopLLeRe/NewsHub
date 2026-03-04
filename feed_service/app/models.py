from sqlalchemy import Column, Integer, String, DateTime, Boolean
from app.database import Base

class NewsItem(Base):
    __tablename__ = "news"
    
    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    image_url = Column(String, nullable=True)
    source_name = Column(String, nullable=False)
    published_at = Column(DateTime, nullable=False)
    category = Column(String, nullable=False)