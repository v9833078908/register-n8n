"""
Database management class.

Handles database initialization, session management, and CRUD operations.
"""
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy import create_engine, func, inspect
from sqlalchemy.orm import sessionmaker, Session

from .models import Base, Video, Post, ProcessingStatus, PostStatus


class Database:
    """Database management class."""

    def __init__(self, db_url: str = "sqlite:///./youtube_threads_mvp.db"):
        """
        Initialize database connection.

        Args:
            db_url: Database connection URL (default: SQLite)
        """
        self.db_url = db_url
        self.engine = create_engine(db_url, echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)

        # Add has_table method to engine for compatibility
        self.engine.has_table = lambda table_name: inspect(self.engine).has_table(table_name)

    def create_tables(self):
        """Create all database tables."""
        Base.metadata.create_all(bind=self.engine)

    def drop_tables(self):
        """Drop all database tables (use with caution!)."""
        Base.metadata.drop_all(bind=self.engine)

    def get_session(self) -> Session:
        """
        Get a new database session.

        Returns:
            SQLAlchemy Session object
        """
        return self.SessionLocal()

    # Video operations

    def add_video(
        self,
        video_id: str,
        title: str,
        url: str,
        published_date: datetime,
        description: Optional[str] = None,
        thumbnail_url: Optional[str] = None,
        duration: Optional[int] = None
    ) -> Video:
        """
        Add a new video to the database.

        Args:
            video_id: YouTube video ID
            title: Video title
            url: Video URL
            published_date: Video publication date
            description: Video description (optional)
            thumbnail_url: Thumbnail URL (optional)
            duration: Video duration in seconds (optional)

        Returns:
            Created Video object
        """
        session = self.get_session()
        try:
            video = Video(
                video_id=video_id,
                title=title,
                url=url,
                published_date=published_date,
                description=description,
                thumbnail_url=thumbnail_url,
                duration=duration,
                processing_status=ProcessingStatus.NEW
            )
            session.add(video)
            session.commit()
            session.refresh(video)
            return video
        finally:
            session.close()

    def get_video_by_id(self, id: int) -> Optional[Video]:
        """Get video by database ID."""
        session = self.get_session()
        try:
            return session.query(Video).filter(Video.id == id).first()
        finally:
            session.close()

    def get_video_by_video_id(self, video_id: str) -> Optional[Video]:
        """
        Get video by YouTube video ID.

        Args:
            video_id: YouTube video ID

        Returns:
            Video object or None if not found
        """
        session = self.get_session()
        try:
            return session.query(Video).filter(Video.video_id == video_id).first()
        finally:
            session.close()

    def video_exists(self, video_id: str) -> bool:
        """
        Check if video exists in database.

        Args:
            video_id: YouTube video ID

        Returns:
            True if video exists, False otherwise
        """
        return self.get_video_by_video_id(video_id) is not None

    def update_video_status(self, video_id: int, status: ProcessingStatus):
        """
        Update video processing status.

        Args:
            video_id: Database video ID
            status: New processing status
        """
        session = self.get_session()
        try:
            video = session.query(Video).filter(Video.id == video_id).first()
            if video:
                video.processing_status = status
                video.updated_at = datetime.utcnow()
                session.commit()
        finally:
            session.close()

    def update_video_transcript(self, video_id: int, transcript: str):
        """Update video transcript."""
        session = self.get_session()
        try:
            video = session.query(Video).filter(Video.id == video_id).first()
            if video:
                video.transcript = transcript
                video.processing_status = ProcessingStatus.TRANSCRIBED
                video.updated_at = datetime.utcnow()
                session.commit()
        finally:
            session.close()

    def get_videos_by_status(self, status: ProcessingStatus) -> List[Video]:
        """Get all videos with specific status."""
        session = self.get_session()
        try:
            return session.query(Video).filter(Video.processing_status == status).all()
        finally:
            session.close()

    def get_pending_videos(self) -> List[Video]:
        """Get videos pending approval (posts generated but not approved)."""
        session = self.get_session()
        try:
            return session.query(Video).filter(
                Video.processing_status == ProcessingStatus.POSTS_GENERATED
            ).all()
        finally:
            session.close()

    def get_recent_videos(self, limit: int = 10) -> List[Video]:
        """
        Get recent videos ordered by published date.

        Args:
            limit: Maximum number of videos to return

        Returns:
            List of Video objects
        """
        session = self.get_session()
        try:
            return session.query(Video).order_by(
                Video.published_date.desc()
            ).limit(limit).all()
        finally:
            session.close()

    # Post operations

    def add_post(
        self,
        video_id: int,
        platform: str,
        content: str,
        status: PostStatus = PostStatus.DRAFT
    ) -> Post:
        """
        Add a new post to the database.

        Args:
            video_id: Database video ID (foreign key)
            platform: Platform name ('threads', 'twitter', 'linkedin')
            content: Post content
            status: Post status (default: DRAFT)

        Returns:
            Created Post object
        """
        session = self.get_session()
        try:
            post = Post(
                video_id=video_id,
                platform=platform,
                content=content,
                status=status
            )
            session.add(post)
            session.commit()
            session.refresh(post)
            return post
        finally:
            session.close()

    def get_post_by_id(self, post_id: int) -> Optional[Post]:
        """Get post by ID."""
        session = self.get_session()
        try:
            return session.query(Post).filter(Post.id == post_id).first()
        finally:
            session.close()

    def get_posts_by_video(self, video_id: int) -> List[Post]:
        """
        Get all posts for a specific video.

        Args:
            video_id: Database video ID

        Returns:
            List of Post objects
        """
        session = self.get_session()
        try:
            return session.query(Post).filter(Post.video_id == video_id).all()
        finally:
            session.close()

    def mark_post_as_published(
        self,
        post_id: int,
        published_url: str
    ):
        """
        Mark post as published.

        Args:
            post_id: Database post ID
            published_url: URL of published post
        """
        session = self.get_session()
        try:
            post = session.query(Post).filter(Post.id == post_id).first()
            if post:
                post.status = PostStatus.PUBLISHED
                post.published_url = published_url
                post.published_at = datetime.utcnow()
                post.updated_at = datetime.utcnow()
                session.commit()
        finally:
            session.close()

    # Statistics

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get database statistics.

        Returns:
            Dictionary with statistics
        """
        session = self.get_session()
        try:
            total_videos = session.query(func.count(Video.id)).scalar()
            total_posts = session.query(func.count(Post.id)).scalar()

            published_posts = session.query(func.count(Post.id)).filter(
                Post.status == PostStatus.PUBLISHED
            ).scalar()

            pending_approvals = session.query(func.count(Video.id)).filter(
                Video.processing_status == ProcessingStatus.POSTS_GENERATED
            ).scalar()

            return {
                'total_videos': total_videos or 0,
                'total_posts': total_posts or 0,
                'published_posts': published_posts or 0,
                'pending_approvals': pending_approvals or 0
            }
        finally:
            session.close()

    # Cleanup operations

    def delete_old_videos(self, days: int = 30):
        """
        Delete videos older than specified days.

        Args:
            days: Number of days to keep
        """
        session = self.get_session()
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            session.query(Video).filter(
                Video.published_date < cutoff_date
            ).delete()
            session.commit()
        finally:
            session.close()
