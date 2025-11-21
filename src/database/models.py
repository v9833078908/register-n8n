"""
Database models for YouTube to Threads MVP.

Uses SQLAlchemy ORM for database operations.
"""
from datetime import datetime
from enum import Enum
from typing import List

from sqlalchemy import Column, Integer, String, Text, DateTime, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import relationship, declarative_base


Base = declarative_base()


class ProcessingStatus(str, Enum):
    """Video processing status enum."""
    NEW = "new"
    TRANSCRIBED = "transcribed"
    POSTS_GENERATED = "posts_generated"
    APPROVED = "approved"
    PUBLISHED = "published"
    REJECTED = "rejected"
    FAILED = "failed"


class PostStatus(str, Enum):
    """Post publishing status enum."""
    DRAFT = "draft"
    APPROVED = "approved"
    PUBLISHED = "published"
    FAILED = "failed"
    REJECTED = "rejected"


class Video(Base):
    """Video model representing YouTube videos."""

    __tablename__ = 'videos'

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(String(255), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    url = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    published_date = Column(DateTime, nullable=False)
    thumbnail_url = Column(String(500), nullable=True)
    duration = Column(Integer, nullable=True)  # Duration in seconds

    # Processing data
    transcript = Column(Text, nullable=True)
    processing_status = Column(
        SQLEnum(ProcessingStatus),
        default=ProcessingStatus.NEW,
        nullable=False,
        index=True
    )

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)

    # Relationships
    posts = relationship("Post", back_populates="video", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Video(id={self.id}, video_id='{self.video_id}', title='{self.title}', status='{self.processing_status.value}')>"


class Post(Base):
    """Post model representing social media posts."""

    __tablename__ = 'posts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(Integer, ForeignKey('videos.id'), nullable=False, index=True)

    # Post data
    platform = Column(String(50), nullable=False)  # 'threads', 'twitter', 'linkedin'
    content = Column(Text, nullable=False)
    status = Column(
        SQLEnum(PostStatus),
        default=PostStatus.DRAFT,
        nullable=False,
        index=True
    )

    # Publishing data
    published_url = Column(String(500), nullable=True)
    published_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    video = relationship("Video", back_populates="posts")

    def __repr__(self):
        return f"<Post(id={self.id}, platform='{self.platform}', status='{self.status.value}')>"
