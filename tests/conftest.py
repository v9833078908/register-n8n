"""
Shared pytest fixtures for all tests.

This file contains fixtures that are used across multiple test modules.
"""
import pytest
from datetime import datetime
from unittest.mock import Mock


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Mock environment variables for testing."""
    monkeypatch.setenv("YOUTUBE_CHANNEL_ID", "UCtest123")
    monkeypatch.setenv("OPENAI_API_KEY", "test_openai_key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test_anthropic_key")
    monkeypatch.setenv("THREADS_ACCESS_TOKEN", "test_threads_token")
    monkeypatch.setenv("THREADS_USER_ID", "test_threads_user")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_telegram_token")
    monkeypatch.setenv("TELEGRAM_ADMIN_CHAT_ID", "123456789")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")


@pytest.fixture
def sample_video_data():
    """Sample video data for testing."""
    return {
        'video_id': 'test_video_123',
        'title': 'Test Medical Video About Vitamin D',
        'url': 'https://www.youtube.com/watch?v=test_video_123',
        'description': 'A test video about the importance of vitamin D',
        'published_date': datetime(2025, 11, 20, 10, 0, 0),
        'thumbnail_url': 'https://i.ytimg.com/vi/test_video_123/hqdefault.jpg',
        'duration': 180
    }


@pytest.fixture
def sample_transcript_text():
    """Sample transcript text for testing."""
    return """
    Здравствуйте! Сегодня я хочу поговорить о важности витамина D для нашего здоровья.

    Витамин D играет ключевую роль в поддержании иммунной системы и здоровья костей.
    Многие люди, особенно в северных регионах, испытывают дефицит витамина D,
    особенно в зимние месяцы когда мало солнечного света.

    Важно помнить, что это общая информация для образовательных целей.
    Всегда консультируйтесь с врачом перед началом приема любых добавок.

    Спасибо за внимание!
    """


@pytest.fixture
def sample_generated_post_threads():
    """Sample generated post for Threads."""
    return """🩺 Витамин D - ключ к здоровью!

Особенно важен зимой, когда мало солнца. Влияет на иммунитет и кости.

💡 Простой анализ покажет ваш уровень витамина D.

⚠️ Это общая информация, не медицинская рекомендация. Проконсультируйтесь с врачом!

#здоровье #витаминD"""


@pytest.fixture
def mock_youtube_rss_feed():
    """Mock YouTube RSS feed XML."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015"
      xmlns:media="http://search.yahoo.com/mrss/"
      xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <yt:videoId>test_video_123</yt:videoId>
    <yt:channelId>UCtest123</yt:channelId>
    <title>Test Medical Video</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=test_video_123"/>
    <author>
      <name>Test Doctor Channel</name>
      <uri>https://www.youtube.com/channel/UCtest123</uri>
    </author>
    <published>2025-11-20T10:00:00+00:00</published>
    <updated>2025-11-20T10:00:00+00:00</updated>
    <media:group>
      <media:title>Test Medical Video</media:title>
      <media:content url="https://www.youtube.com/v/test_video_123" type="application/x-shockwave-flash"/>
      <media:thumbnail url="https://i1.ytimg.com/vi/test_video_123/hqdefault.jpg"/>
      <media:description>Test video about medical topic</media:description>
    </media:group>
  </entry>
</feed>"""


@pytest.fixture
def mock_youtube_transcript():
    """Mock YouTube transcript segments."""
    return [
        {
            'text': 'Здравствуйте! Сегодня о витамине D.',
            'start': 0.0,
            'duration': 3.5
        },
        {
            'text': 'Витамин D важен для иммунитета.',
            'start': 3.5,
            'duration': 3.2
        },
        {
            'text': 'Особенно зимой когда мало солнца.',
            'start': 6.7,
            'duration': 2.8
        },
        {
            'text': 'Это общая информация.',
            'start': 9.5,
            'duration': 2.0
        },
        {
            'text': 'Проконсультируйтесь с врачом.',
            'start': 11.5,
            'duration': 2.5
        }
    ]


@pytest.fixture
def mock_claude_response():
    """Mock Claude API response."""
    return Mock(
        content=[
            Mock(text="""🩺 Витамин D - ключ к здоровью!

Особенно важен зимой. Влияет на иммунитет и кости.

💡 Анализ крови покажет ваш уровень.

⚠️ Это общая информация, не медицинская рекомендация. Проконсультируйтесь с врачом!

#здоровье""")
        ]
    )


@pytest.fixture
def mock_threads_api_success_response():
    """Mock successful Threads API response."""
    return {
        'id': 'thread_123456789',
        'permalink': 'https://www.threads.net/@test_user/post/thread_123456789'
    }


@pytest.fixture
def sample_safe_transcript():
    """Sample safe medical transcript for testing."""
    return """
    Сегодня поговорим о важности регулярных физических упражнений для здоровья.

    Исследования показывают, что умеренная физическая активность полезна для
    сердечно-сосудистой системы и общего самочувствия.

    Это общая информация для образовательных целей.
    Проконсультируйтесь с врачом перед началом новой программы тренировок.
    """


@pytest.fixture
def sample_unsafe_transcript_dosage():
    """Sample unsafe transcript with dosage."""
    return """
    Принимайте 10000 МЕ витамина D ежедневно.
    Это точная дозировка которую вам нужно принимать.
    Начните сразу без консультации с врачом.
    """


@pytest.fixture
def sample_unsafe_transcript_diagnosis():
    """Sample unsafe transcript with diagnosis."""
    return """
    Если у вас эти симптомы, у вас точно диабет.
    Начните принимать метформин немедленно.
    Вам нужно это лекарство для лечения.
    """
