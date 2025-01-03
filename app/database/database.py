from datetime import datetime
from typing import List

from dotenv import load_dotenv
from pydantic import BaseModel
from sqlalchemy import Column, TIMESTAMP, text
from sqlalchemy.orm import selectinload, Session
from sqlmodel import Field, SQLModel, create_engine, Relationship, select
import os

# Load environment variables
load_dotenv()

# Database configuration
DB_URL = os.getenv("DATABASE_URL")
engine = create_engine(DB_URL)


class NewsAnalysis(BaseModel):
    """Pydantic model for news analysis data validation"""
    issue: str
    importance: str
    keyword: str
    effects: List[str]


class NewsSQLModel(SQLModel, table=True):
    """SQLModel for news table"""
    __tablename__ = "news"

    class Config:
        arbitrary_types_allowed = True

    id: int | None = Field(default=None, primary_key=True)
    issue: str
    importance: str
    keyword: str
    time: datetime = Field(
        default_factory=datetime.now,
        sa_column=Column(
            'time',
            TIMESTAMP,
            server_default=text('CURRENT_TIMESTAMP'),
            nullable=False
        )
    )
    effects: List["NewsSQLModelEffects"] = Relationship(back_populates="news")


class NewsSQLModelEffects(SQLModel, table=True):
    """SQLModel for news effects table"""
    __tablename__ = "effects"

    class Config:
        arbitrary_types_allowed = True

    id: int | None = Field(default=None, primary_key=True)
    news_id: int = Field(foreign_key="news.id")
    effect: str
    news: NewsSQLModel = Relationship(back_populates="effects")


def get_session() -> Session:
    """Database session dependency"""
    with Session(engine) as session:
        yield session


class NewsSQLModelDB:
    """Database operations for news models"""

    @staticmethod
    def create_db_and_tables() -> None:
        """Create database tables"""
        SQLModel.metadata.create_all(engine)

    @staticmethod
    def save_news_analysis(session: Session, analysis: NewsAnalysis) -> NewsSQLModel:
        """
        Save news analysis to database

        Args:
            session: Database session
            analysis: News analysis data

        Returns:
            Created news model instance
        """
        # Create news entry
        news = NewsSQLModel(
            issue=analysis.issue,
            importance=analysis.importance,
            keyword=analysis.keyword
        )
        session.add(news)
        session.commit()
        session.refresh(news)

        # Create effect entries
        effects = [
            NewsSQLModelEffects(news_id=news.id, effect=effect)
            for effect in analysis.effects
        ]
        session.add_all(effects)
        session.commit()

        return news

    @staticmethod
    def get_news(session: Session) -> NewsSQLModel | None:
        """
        Get most recent news entry

        Args:
            session: Database session

        Returns:
            Most recent news entry or None if no entries exist
        """
        statement = (
            select(NewsSQLModel)
            .options(selectinload(NewsSQLModel.effects))
            .order_by(NewsSQLModel.id.desc())
            .limit(1)
        )
        return session.exec(statement).first()