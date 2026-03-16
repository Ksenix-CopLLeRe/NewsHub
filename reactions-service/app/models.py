from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLAlchemyEnum, UniqueConstraint
from sqlalchemy.sql import func
from app.database import Base
import enum

class ReactionTypeEnum(enum.Enum):
    important = "important"
    interesting = "interesting"
    shocking = "shocking"
    useful = "useful"
    liked = "liked"

class Reaction(Base):
    __tablename__ = "reactions"
    
    __table_args__ = (
        UniqueConstraint('user_id', 'news_id', name='unique_user_news_reaction'),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    news_id = Column(String, nullable=False, index=True)
    # Важно: native_enum=False для совместимости с SQLite
    reaction_type = Column(SQLAlchemyEnum(ReactionTypeEnum, native_enum=False), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())