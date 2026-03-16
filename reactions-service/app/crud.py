from sqlalchemy.orm import Session
from sqlalchemy import and_
from app import models, schemas

def get_reaction(db: Session, reaction_id: int):
    return db.get(models.Reaction, reaction_id)

def get_user_reaction(db: Session, user_id: int, news_id: str):
    return db.query(models.Reaction).filter(
        and_(
            models.Reaction.user_id == user_id,
            models.Reaction.news_id == news_id
        )
    ).first()

def create_reaction(db: Session, reaction: schemas.ReactionCreate):
    db_reaction = models.Reaction(**reaction.model_dump())
    db.add(db_reaction)
    db.commit()
    db.refresh(db_reaction)
    return db_reaction

def update_reaction(db: Session, db_reaction: models.Reaction, reaction_update: schemas.ReactionUpdate):
    update_data = reaction_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_reaction, field, value)
    db.commit()
    db.refresh(db_reaction)
    return db_reaction

def delete_reaction(db: Session, db_reaction: models.Reaction):
    db.delete(db_reaction)
    db.commit()

def get_reactions_by_news(db: Session, news_id: str, skip: int = 0, limit: int = 10):
    return db.query(models.Reaction).filter(
        models.Reaction.news_id == news_id
    ).offset(skip).limit(limit).all()

def count_reactions_by_news(db: Session, news_id: str):
    return db.query(models.Reaction).filter(
        models.Reaction.news_id == news_id
    ).count()

def get_reaction_counts(db: Session, news_id: str):
    from sqlalchemy import func
    
    results = db.query(
        models.Reaction.reaction_type,
        func.count(models.Reaction.id).label('count')
    ).filter(
        models.Reaction.news_id == news_id
    ).group_by(
        models.Reaction.reaction_type
    ).all()
    
    counts = {rt.value: 0 for rt in models.ReactionTypeEnum}
    total = 0
    
    for reaction_type, count in results:
        counts[reaction_type.value] = count
        total += count
    
    return counts, total