from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class NewsBase(BaseModel):
    url: str
    title: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    source_name: str
    published_at: datetime
    category: str

class NewsCreate(NewsBase):
    pass

class NewsResponse(NewsBase):
    id: int
    
    class Config:
        from_attributes = True

class NewsUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    category: Optional[str] = None