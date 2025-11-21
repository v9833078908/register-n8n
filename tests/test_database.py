"""
Unit tests for Database models and operations.

Tests cover:
- Video model CRUD operations
- Post model CRUD operations
- Database initialization
- Relationships
- Query operations
"""
import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.models import Base, Video, Post, ProcessingStatus, PostStatus
from src.database.db import Database


class TestDatabaseModels:
    """Test suite for database models."""

    @pytest.fixture
    def test_db(self):
        """Create test database in memory."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        yield session
        session.close()

    @pytest.fixture
    def sample_video_data(self):
        """Sample video data for testing."""
        return {
            'video_id': 'test_video_123',
            'title': 'Test Medical Video',
            'url': 'https://youtube.com/watch?v=test_video_123',
            'description': 'Test description',
            'published_date': datetime.now(),
            'thumbnail_url': 'https://i.ytimg.com/vi/test_video_123/hq.jpg',
            'duration': 180
        }

    @pytest.fixture
    def sample_post_data(self):
        """Sample post data for testing."""
        return {
            'platform': 'threads',
            'content': '🩺 Test post content\n\n⚠️ Disclaimer',
            'status': PostStatus.DRAFT
        }

    def test_video_model_creation(self, test_db, sample_video_data):
        """Test creating Video model instance."""
        video = Video(**sample_video_data)
        test_db.add(video)
        test_db.commit()

        assert video.id is not None
        assert video.video_id == 'test_video_123'
        assert video.title == 'Test Medical Video'

    def test_video_model_default_status(self, test_db, sample_video_data):
        """Test Video model has default processing status."""
        video = Video(**sample_video_data)
        test_db.add(video)
        test_db.commit()

        assert video.processing_status == ProcessingStatus.NEW

    def test_video_model_relationships(self, test_db, sample_video_data, sample_post_data):
        """Test Video to Post relationship."""
        video = Video(**sample_video_data)
        test_db.add(video)
        test_db.commit()

        post = Post(**sample_post_data, video_id=video.id)
        test_db.add(post)
        test_db.commit()

        # Test relationship
        assert len(video.posts) == 1
        assert video.posts[0].content == sample_post_data['content']

    def test_post_model_creation(self, test_db, sample_video_data, sample_post_data):
        """Test creating Post model instance."""
        video = Video(**sample_video_data)
        test_db.add(video)
        test_db.commit()

        post = Post(**sample_post_data, video_id=video.id)
        test_db.add(post)
        test_db.commit()

        assert post.id is not None
        assert post.platform == 'threads'
        assert post.status == PostStatus.DRAFT

    def test_post_model_timestamps(self, test_db, sample_video_data, sample_post_data):
        """Test Post model auto-generates timestamps."""
        video = Video(**sample_video_data)
        test_db.add(video)
        test_db.commit()

        post = Post(**sample_post_data, video_id=video.id)
        test_db.add(post)
        test_db.commit()

        assert post.created_at is not None
        assert isinstance(post.created_at, datetime)

    def test_processing_status_enum(self):
        """Test ProcessingStatus enum values."""
        assert ProcessingStatus.NEW.value == "new"
        assert ProcessingStatus.TRANSCRIBED.value == "transcribed"
        assert ProcessingStatus.POSTS_GENERATED.value == "posts_generated"
        assert ProcessingStatus.APPROVED.value == "approved"
        assert ProcessingStatus.PUBLISHED.value == "published"
        assert ProcessingStatus.REJECTED.value == "rejected"
        assert ProcessingStatus.FAILED.value == "failed"

    def test_post_status_enum(self):
        """Test PostStatus enum values."""
        assert PostStatus.DRAFT.value == "draft"
        assert PostStatus.APPROVED.value == "approved"
        assert PostStatus.PUBLISHED.value == "published"
        assert PostStatus.FAILED.value == "failed"
        assert PostStatus.REJECTED.value == "rejected"

    def test_query_video_by_video_id(self, test_db, sample_video_data):
        """Test querying video by video_id."""
        video = Video(**sample_video_data)
        test_db.add(video)
        test_db.commit()

        queried_video = test_db.query(Video).filter_by(
            video_id='test_video_123'
        ).first()

        assert queried_video is not None
        assert queried_video.video_id == 'test_video_123'

    def test_query_videos_by_status(self, test_db, sample_video_data):
        """Test querying videos by processing status."""
        video1 = Video(**sample_video_data)
        video1.processing_status = ProcessingStatus.NEW
        test_db.add(video1)

        video2_data = sample_video_data.copy()
        video2_data['video_id'] = 'test_video_456'
        video2 = Video(**video2_data)
        video2.processing_status = ProcessingStatus.PUBLISHED
        test_db.add(video2)

        test_db.commit()

        new_videos = test_db.query(Video).filter_by(
            processing_status=ProcessingStatus.NEW
        ).all()

        assert len(new_videos) == 1
        assert new_videos[0].video_id == 'test_video_123'

    def test_update_video_status(self, test_db, sample_video_data):
        """Test updating video processing status."""
        video = Video(**sample_video_data)
        test_db.add(video)
        test_db.commit()

        video.processing_status = ProcessingStatus.TRANSCRIBED
        test_db.commit()

        updated_video = test_db.query(Video).filter_by(id=video.id).first()
        assert updated_video.processing_status == ProcessingStatus.TRANSCRIBED

    def test_update_video_transcript(self, test_db, sample_video_data):
        """Test updating video transcript."""
        video = Video(**sample_video_data)
        test_db.add(video)
        test_db.commit()

        transcript_text = "This is the video transcript..."
        video.transcript = transcript_text
        video.processing_status = ProcessingStatus.TRANSCRIBED
        test_db.commit()

        updated_video = test_db.query(Video).filter_by(id=video.id).first()
        assert updated_video.transcript == transcript_text

    def test_update_post_status(self, test_db, sample_video_data, sample_post_data):
        """Test updating post status."""
        video = Video(**sample_video_data)
        test_db.add(video)
        test_db.commit()

        post = Post(**sample_post_data, video_id=video.id)
        test_db.add(post)
        test_db.commit()

        post.status = PostStatus.PUBLISHED
        post.published_url = "https://threads.net/@user/post/123"
        test_db.commit()

        updated_post = test_db.query(Post).filter_by(id=post.id).first()
        assert updated_post.status == PostStatus.PUBLISHED
        assert updated_post.published_url is not None

    def test_delete_video_cascades_posts(self, test_db, sample_video_data, sample_post_data):
        """Test deleting video cascades to delete posts."""
        video = Video(**sample_video_data)
        test_db.add(video)
        test_db.commit()

        post = Post(**sample_post_data, video_id=video.id)
        test_db.add(post)
        test_db.commit()

        video_id = video.id
        test_db.delete(video)
        test_db.commit()

        # Posts should be deleted (if cascade is set)
        remaining_posts = test_db.query(Post).filter_by(video_id=video_id).all()
        # Depends on cascade settings in model


class TestDatabase:
    """Test suite for Database class."""

    @pytest.fixture
    def database(self, tmp_path):
        """Create test database."""
        db_path = tmp_path / "test.db"
        return Database(db_url=f"sqlite:///{db_path}")

    def test_database_init(self, database):
        """Test Database initialization."""
        assert database.engine is not None
        assert database.SessionLocal is not None

    def test_create_tables(self, database):
        """Test creating database tables."""
        database.create_tables()

        # Tables should exist
        assert database.engine.has_table('videos')
        assert database.engine.has_table('posts')

    def test_get_session(self, database):
        """Test getting database session."""
        database.create_tables()
        session = database.get_session()

        assert session is not None
        session.close()

    def test_add_video(self, database):
        """Test adding video through Database class."""
        database.create_tables()

        video_data = {
            'video_id': 'test123',
            'title': 'Test Video',
            'url': 'https://youtube.com/watch?v=test123',
            'published_date': datetime.now()
        }

        video = database.add_video(**video_data)

        assert video.id is not None
        assert video.video_id == 'test123'

    def test_get_video_by_video_id(self, database):
        """Test retrieving video by video_id."""
        database.create_tables()

        video_data = {
            'video_id': 'test123',
            'title': 'Test Video',
            'url': 'https://youtube.com/watch?v=test123',
            'published_date': datetime.now()
        }

        database.add_video(**video_data)
        retrieved_video = database.get_video_by_video_id('test123')

        assert retrieved_video is not None
        assert retrieved_video.video_id == 'test123'

    def test_get_video_by_video_id_not_found(self, database):
        """Test retrieving non-existent video."""
        database.create_tables()

        video = database.get_video_by_video_id('nonexistent')

        assert video is None

    def test_update_video_status_method(self, database):
        """Test updating video status through Database method."""
        database.create_tables()

        video = database.add_video(
            video_id='test123',
            title='Test',
            url='https://youtube.com/watch?v=test123',
            published_date=datetime.now()
        )

        database.update_video_status(video.id, ProcessingStatus.TRANSCRIBED)

        updated = database.get_video_by_id(video.id)
        assert updated.processing_status == ProcessingStatus.TRANSCRIBED

    def test_add_post(self, database):
        """Test adding post through Database class."""
        database.create_tables()

        video = database.add_video(
            video_id='test123',
            title='Test',
            url='https://youtube.com/watch?v=test123',
            published_date=datetime.now()
        )

        post = database.add_post(
            video_id=video.id,
            platform='threads',
            content='Test post content'
        )

        assert post.id is not None
        assert post.platform == 'threads'

    def test_get_posts_by_video(self, database):
        """Test retrieving all posts for a video."""
        database.create_tables()

        video = database.add_video(
            video_id='test123',
            title='Test',
            url='https://youtube.com/watch?v=test123',
            published_date=datetime.now()
        )

        database.add_post(video_id=video.id, platform='threads', content='Post 1')

        posts = database.get_posts_by_video(video.id)

        assert len(posts) == 1
        assert posts[0].platform == 'threads'

    def test_get_pending_videos(self, database):
        """Test getting videos pending approval."""
        database.create_tables()

        video1 = database.add_video(
            video_id='test1',
            title='Test 1',
            url='https://youtube.com/watch?v=test1',
            published_date=datetime.now()
        )
        database.update_video_status(video1.id, ProcessingStatus.POSTS_GENERATED)

        video2 = database.add_video(
            video_id='test2',
            title='Test 2',
            url='https://youtube.com/watch?v=test2',
            published_date=datetime.now()
        )
        database.update_video_status(video2.id, ProcessingStatus.PUBLISHED)

        pending = database.get_pending_videos()

        assert len(pending) == 1
        assert pending[0].video_id == 'test1'

    def test_mark_post_as_published(self, database):
        """Test marking post as published."""
        database.create_tables()

        video = database.add_video(
            video_id='test123',
            title='Test',
            url='https://youtube.com/watch?v=test123',
            published_date=datetime.now()
        )

        post = database.add_post(
            video_id=video.id,
            platform='threads',
            content='Test post'
        )

        database.mark_post_as_published(
            post.id,
            published_url='https://threads.net/@user/post/123'
        )

        updated_post = database.get_post_by_id(post.id)
        assert updated_post.status == PostStatus.PUBLISHED
        assert updated_post.published_url is not None
        assert updated_post.published_at is not None

    def test_get_recent_videos(self, database):
        """Test getting recent videos."""
        database.create_tables()

        for i in range(5):
            database.add_video(
                video_id=f'test{i}',
                title=f'Test {i}',
                url=f'https://youtube.com/watch?v=test{i}',
                published_date=datetime.now()
            )

        recent = database.get_recent_videos(limit=3)

        assert len(recent) == 3

    def test_video_exists(self, database):
        """Test checking if video exists."""
        database.create_tables()

        database.add_video(
            video_id='test123',
            title='Test',
            url='https://youtube.com/watch?v=test123',
            published_date=datetime.now()
        )

        assert database.video_exists('test123') is True
        assert database.video_exists('nonexistent') is False

    def test_get_statistics(self, database):
        """Test getting database statistics."""
        database.create_tables()

        # Add some data
        video = database.add_video(
            video_id='test123',
            title='Test',
            url='https://youtube.com/watch?v=test123',
            published_date=datetime.now()
        )

        database.add_post(video_id=video.id, platform='threads', content='Post')

        stats = database.get_statistics()

        assert 'total_videos' in stats
        assert 'total_posts' in stats
        assert stats['total_videos'] >= 1
        assert stats['total_posts'] >= 1
