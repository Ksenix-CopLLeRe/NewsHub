from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict
from enum import Enum

class ReactionType(str, Enum):
    important = "important"
    interesting = "interesting"
    shocking = "shocking"
    useful = "useful"
    liked = "liked"

class ReactionBase(BaseModel):
    user_id: int
    news_id: str
    reaction_type: ReactionType

class ReactionCreate(ReactionBase):
    pass

class ReactionUpdate(BaseModel):
    reaction_type: Optional[ReactionType] = None

class ReactionResponse(ReactionBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class ReactionCountsResponse(BaseModel):
    news_id: str
    counts: Dict[ReactionType, int]
    total: int

class ReactionListResponse(BaseModel):
    items: list[ReactionResponse]
    total: int
    page: int
    size: int