# app/schemas.py
from pydantic import BaseModel, HttpUrl, Field
from datetime import datetime
from typing import Optional, List

class NewsBase(BaseModel):
    url: str
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    image_url: Optional[str] = None
    source_name: str = "Lenta.ru"
    published_at: datetime
    category: str = Field(..., min_length=1, max_length=50)

class NewsCreate(NewsBase):
    pass

class NewsUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    image_url: Optional[str] = None
    category: Optional[str] = Field(None, max_length=50)

class NewsResponse(NewsBase):
    id: int
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class NewsListResponse(BaseModel):
    items: List[NewsResponse]
    total: int
    page: int
    size: int

class CategoryInfo(BaseModel):
    name: str
    count: int

class CategoriesResponse(BaseModel):
    categories: List[CategoryInfo]
    total: int

class RSSUpdateResponse(BaseModel):
    category: str
    parsed: int
    saved: int
    errors: int
    duration_ms: int

class BulkUpdateResponse(BaseModel):
    status: str
    results: dict
    total_parsed: int
    total_saved: int
    total_errors: int
    duration_ms: int