"""
Unit tests for YouTube RSS feed detector.

Tests cover:
- RSS feed parsing
- New video detection
- Date filtering
- Error handling
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from src.youtube.detector import YouTubeDetector, Video


class TestYouTubeDetector:
    """Test suite for YouTubeDetector class."""

    @pytest.fixture
    def detector(self):
        """Create YouTubeDetector instance for testing."""
        return YouTubeDetector(channel_id="UCtest123")

    @pytest.fixture
    def mock_rss_feed(self):
        """Mock RSS feed response."""
        return """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015"
      xmlns:media="http://search.yahoo.com/mrss/"
      xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <yt:videoId>abc123</yt:videoId>
    <yt:channelId>UCtest123</yt:channelId>
    <title>Test Video Title</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=abc123"/>
    <author>
      <name>Test Channel</name>
      <uri>https://www.youtube.com/channel/UCtest123</uri>
    </author>
    <published>2025-11-20T10:00:00+00:00</published>
    <updated>2025-11-20T10:00:00+00:00</updated>
    <media:group>
      <media:title>Test Video Title</media:title>
      <media:content url="https://www.youtube.com/v/abc123?version=3" type="application/x-shockwave-flash" width="640" height="390"/>
      <media:thumbnail url="https://i1.ytimg.com/vi/abc123/hqdefault.jpg" width="480" height="360"/>
      <media:description>Test video description</media:description>
    </media:group>
  </entry>
</feed>"""

    def test_init_with_valid_channel_id(self, detector):
        """Test initialization with valid channel ID."""
        assert detector.channel_id == "UCtest123"
        assert detector.rss_url == "https://www.youtube.com/feeds/videos.xml?channel_id=UCtest123"

    def test_init_with_invalid_channel_id(self):
        """Test initialization with invalid channel ID raises ValueError."""
        with pytest.raises(ValueError, match="Channel ID cannot be empty"):
            YouTubeDetector(channel_id="")

    @patch('requests.get')
    def test_fetch_rss_feed_success(self, mock_get, detector, mock_rss_feed):
        """Test successful RSS feed fetch."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = mock_rss_feed
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        feed_data = detector.fetch_rss_feed()

        assert feed_data == mock_rss_feed
        mock_get.assert_called_once_with(detector.rss_url, timeout=10)

    @patch('requests.get')
    def test_fetch_rss_feed_http_error(self, mock_get, detector):
        """Test RSS feed fetch with HTTP error."""
        mock_get.side_effect = Exception("HTTP 404")

        with pytest.raises(Exception):
            detector.fetch_rss_feed()

    @patch('requests.get')
    def test_fetch_rss_feed_timeout(self, mock_get, detector):
        """Test RSS feed fetch timeout."""
        import requests
        mock_get.side_effect = requests.Timeout("Connection timeout")

        with pytest.raises(requests.Timeout):
            detector.fetch_rss_feed()

    def test_parse_rss_feed_valid(self, detector, mock_rss_feed):
        """Test parsing valid RSS feed."""
        videos = detector.parse_rss_feed(mock_rss_feed)

        assert len(videos) == 1
        video = videos[0]
        assert isinstance(video, Video)
        assert video.video_id == "abc123"
        assert video.title == "Test Video Title"
        assert video.url == "https://www.youtube.com/watch?v=abc123"
        assert video.description == "Test video description"
        assert isinstance(video.published_date, datetime)

    def test_parse_rss_feed_empty(self, detector):
        """Test parsing empty RSS feed."""
        empty_feed = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"></feed>"""

        videos = detector.parse_rss_feed(empty_feed)
        assert videos == []

    def test_parse_rss_feed_invalid_xml(self, detector):
        """Test parsing invalid XML raises exception."""
        invalid_xml = "This is not valid XML"

        with pytest.raises(Exception):
            detector.parse_rss_feed(invalid_xml)

    def test_filter_new_videos_within_timeframe(self, detector):
        """Test filtering videos published within timeframe."""
        now = datetime.now()
        recent_video = Video(
            video_id="recent123",
            title="Recent Video",
            url="https://youtube.com/watch?v=recent123",
            description="Recent",
            published_date=now - timedelta(minutes=10),
            thumbnail_url="https://i.ytimg.com/vi/recent123/hq.jpg"
        )
        old_video = Video(
            video_id="old123",
            title="Old Video",
            url="https://youtube.com/watch?v=old123",
            description="Old",
            published_date=now - timedelta(hours=25),
            thumbnail_url="https://i.ytimg.com/vi/old123/hq.jpg"
        )

        videos = [recent_video, old_video]
        new_videos = detector.filter_new_videos(videos, hours=24)

        assert len(new_videos) == 1
        assert new_videos[0].video_id == "recent123"

    def test_filter_new_videos_all_old(self, detector):
        """Test filtering when all videos are old."""
        now = datetime.now()
        old_video = Video(
            video_id="old123",
            title="Old Video",
            url="https://youtube.com/watch?v=old123",
            description="Old",
            published_date=now - timedelta(hours=48),
            thumbnail_url="https://i.ytimg.com/vi/old123/hq.jpg"
        )

        videos = [old_video]
        new_videos = detector.filter_new_videos(videos, hours=24)

        assert len(new_videos) == 0

    def test_filter_new_videos_custom_timeframe(self, detector):
        """Test filtering with custom timeframe."""
        now = datetime.now()
        video = Video(
            video_id="test123",
            title="Test Video",
            url="https://youtube.com/watch?v=test123",
            description="Test",
            published_date=now - timedelta(minutes=30),
            thumbnail_url="https://i.ytimg.com/vi/test123/hq.jpg"
        )

        videos = [video]

        # Should be included with 1 hour timeframe
        new_videos = detector.filter_new_videos(videos, hours=1)
        assert len(new_videos) == 1

        # Should be excluded with 15 minute timeframe
        new_videos = detector.filter_new_videos(videos, hours=0.25)
        assert len(new_videos) == 0

    @patch.object(YouTubeDetector, 'fetch_rss_feed')
    @patch.object(YouTubeDetector, 'parse_rss_feed')
    @patch.object(YouTubeDetector, 'filter_new_videos')
    def test_check_for_new_videos_integration(
        self,
        mock_filter,
        mock_parse,
        mock_fetch,
        detector
    ):
        """Test full check_for_new_videos workflow."""
        mock_fetch.return_value = "mock_feed_data"
        mock_parse.return_value = [Mock(spec=Video)]
        mock_filter.return_value = [Mock(spec=Video)]

        result = detector.check_for_new_videos(hours=24)

        mock_fetch.assert_called_once()
        mock_parse.assert_called_once_with("mock_feed_data")
        mock_filter.assert_called_once()
        assert len(result) == 1

    def test_video_dataclass_attributes(self):
        """Test Video dataclass has correct attributes."""
        video = Video(
            video_id="test123",
            title="Test Title",
            url="https://youtube.com/watch?v=test123",
            description="Test Description",
            published_date=datetime.now(),
            thumbnail_url="https://i.ytimg.com/vi/test123/hq.jpg"
        )

        assert video.video_id == "test123"
        assert video.title == "Test Title"
        assert video.url == "https://youtube.com/watch?v=test123"
        assert video.description == "Test Description"
        assert isinstance(video.published_date, datetime)
        assert video.thumbnail_url == "https://i.ytimg.com/vi/test123/hq.jpg"

    @pytest.mark.parametrize("channel_id,expected_url", [
        ("UCtest123", "https://www.youtube.com/feeds/videos.xml?channel_id=UCtest123"),
        ("UC_x5XG1OV2P6uZZ5FSM9Ttw", "https://www.youtube.com/feeds/videos.xml?channel_id=UC_x5XG1OV2P6uZZ5FSM9Ttw"),
    ])
    def test_rss_url_construction(self, channel_id, expected_url):
        """Test RSS URL is constructed correctly for different channel IDs."""
        detector = YouTubeDetector(channel_id=channel_id)
        assert detector.rss_url == expected_url
