"""
Unit tests for AI Transcriber using youtube-transcript-api (Priority).

Tests cover:
- Fetching YouTube subtitles
- Fallback to Whisper API if needed
- Error handling
- Subtitle formatting
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.ai.transcriber import Transcriber, TranscriptionResult


class TestTranscriberV2:
    """Test suite for Transcriber class using youtube-transcript-api."""

    @pytest.fixture
    def transcriber(self):
        """Create Transcriber instance for testing."""
        return Transcriber(
            openai_api_key="test_openai_key",
            use_youtube_captions=True  # Priority: YouTube captions
        )

    @pytest.fixture
    def mock_youtube_transcript(self):
        """Mock YouTube transcript response."""
        return [
            {'text': 'Сегодня я хочу поговорить о витамине D.', 'start': 0.0, 'duration': 3.5},
            {'text': 'Это очень важный витамин для здоровья.', 'start': 3.5, 'duration': 3.2},
            {'text': 'Особенно важен зимой.', 'start': 6.7, 'duration': 2.1},
            {'text': 'Проконсультируйтесь с врачом.', 'start': 8.8, 'duration': 2.5}
        ]

    def test_init_with_youtube_captions_enabled(self, transcriber):
        """Test initialization with YouTube captions enabled."""
        assert transcriber.use_youtube_captions is True

    def test_init_without_openai_key_when_youtube_only(self):
        """Test initialization without OpenAI key when using only YouTube captions."""
        # Should not raise error if only using YouTube captions
        transcriber = Transcriber(openai_api_key=None, use_youtube_captions=True)
        assert transcriber.openai_api_key is None
        assert transcriber.use_youtube_captions is True

    def test_init_without_openai_key_when_fallback_needed(self):
        """Test initialization fails without OpenAI key when fallback enabled."""
        with pytest.raises(ValueError, match="OpenAI API key required for fallback"):
            Transcriber(openai_api_key=None, use_youtube_captions=True, enable_whisper_fallback=True)

    @patch('youtube_transcript_api.YouTubeTranscriptApi.get_transcript')
    def test_get_youtube_transcript_success(self, mock_get_transcript, transcriber, mock_youtube_transcript):
        """Test successful YouTube transcript fetch."""
        mock_get_transcript.return_value = mock_youtube_transcript

        result = transcriber.get_youtube_transcript(video_id="test123", language="ru")

        assert isinstance(result, TranscriptionResult)
        assert "витамине D" in result.text
        assert "врачом" in result.text
        assert result.language == "ru"
        assert result.source == "youtube_captions"
        mock_get_transcript.assert_called_once_with("test123", languages=["ru"])

    @patch('youtube_transcript_api.YouTubeTranscriptApi.get_transcript')
    def test_get_youtube_transcript_auto_language(self, mock_get_transcript, transcriber, mock_youtube_transcript):
        """Test YouTube transcript fetch with automatic language detection."""
        mock_get_transcript.return_value = mock_youtube_transcript

        result = transcriber.get_youtube_transcript(video_id="test123")

        # Should try multiple languages
        assert result.text is not None
        assert result.source == "youtube_captions"

    @patch('youtube_transcript_api.YouTubeTranscriptApi.get_transcript')
    def test_get_youtube_transcript_not_available(self, mock_get_transcript, transcriber):
        """Test YouTube transcript fetch when captions not available."""
        from youtube_transcript_api import TranscriptsDisabled
        mock_get_transcript.side_effect = TranscriptsDisabled("test123")

        with pytest.raises(TranscriptsDisabled):
            transcriber.get_youtube_transcript(video_id="test123")

    @patch('youtube_transcript_api.YouTubeTranscriptApi.get_transcript')
    def test_get_youtube_transcript_video_not_found(self, mock_get_transcript, transcriber):
        """Test YouTube transcript fetch when video not found."""
        from youtube_transcript_api import NoTranscriptFound
        mock_get_transcript.side_effect = NoTranscriptFound("test123", ["ru"], [])

        with pytest.raises(NoTranscriptFound):
            transcriber.get_youtube_transcript(video_id="test123", language="ru")

    def test_format_transcript_segments_to_text(self, transcriber, mock_youtube_transcript):
        """Test formatting transcript segments to plain text."""
        formatted_text = transcriber.format_transcript_to_text(mock_youtube_transcript)

        assert isinstance(formatted_text, str)
        assert "Сегодня я хочу поговорить о витамине D." in formatted_text
        assert "Проконсультируйтесь с врачом." in formatted_text
        # Should be joined with spaces
        assert formatted_text.count('\n') < len(mock_youtube_transcript)

    def test_format_transcript_empty_segments(self, transcriber):
        """Test formatting empty transcript segments."""
        empty_segments = []

        formatted_text = transcriber.format_transcript_to_text(empty_segments)

        assert formatted_text == ""

    def test_format_transcript_with_timestamps(self, transcriber, mock_youtube_transcript):
        """Test formatting transcript with timestamps."""
        formatted_text = transcriber.format_transcript_with_timestamps(mock_youtube_transcript)

        assert "[0.0s]" in formatted_text
        assert "[3.5s]" in formatted_text
        assert "Сегодня я хочу поговорить о витамине D." in formatted_text

    @patch('youtube_transcript_api.YouTubeTranscriptApi.list_transcripts')
    def test_get_available_languages(self, mock_list_transcripts, transcriber):
        """Test getting available transcript languages for video."""
        mock_transcript_list = Mock()
        mock_transcript_list.__iter__ = Mock(return_value=iter([
            Mock(language_code='ru'),
            Mock(language_code='en')
        ]))
        mock_list_transcripts.return_value = mock_transcript_list

        languages = transcriber.get_available_languages(video_id="test123")

        assert 'ru' in languages
        assert 'en' in languages
        assert len(languages) == 2

    @patch.object(Transcriber, 'get_youtube_transcript')
    @patch.object(Transcriber, 'transcribe_with_whisper')
    def test_transcribe_with_fallback_success_youtube(
        self,
        mock_whisper,
        mock_youtube,
        transcriber,
        mock_youtube_transcript
    ):
        """Test transcription with fallback - YouTube succeeds."""
        transcriber.enable_whisper_fallback = True
        mock_youtube.return_value = TranscriptionResult(
            text="YouTube transcript",
            language="ru",
            source="youtube_captions"
        )

        result = transcriber.transcribe(video_id="test123", language="ru")

        assert result.text == "YouTube transcript"
        assert result.source == "youtube_captions"
        mock_youtube.assert_called_once()
        mock_whisper.assert_not_called()  # Should not fallback

    @patch.object(Transcriber, 'get_youtube_transcript')
    @patch.object(Transcriber, 'transcribe_with_whisper')
    def test_transcribe_with_fallback_youtube_fails(
        self,
        mock_whisper,
        mock_youtube,
        transcriber
    ):
        """Test transcription with fallback - YouTube fails, Whisper succeeds."""
        transcriber.enable_whisper_fallback = True

        from youtube_transcript_api import TranscriptsDisabled
        mock_youtube.side_effect = TranscriptsDisabled("test123")

        mock_whisper.return_value = TranscriptionResult(
            text="Whisper transcript",
            language="ru",
            source="whisper_api"
        )

        result = transcriber.transcribe(video_id="test123", language="ru")

        assert result.text == "Whisper transcript"
        assert result.source == "whisper_api"
        mock_youtube.assert_called_once()
        mock_whisper.assert_called_once()

    @patch.object(Transcriber, 'get_youtube_transcript')
    def test_transcribe_without_fallback_youtube_fails(
        self,
        mock_youtube,
        transcriber
    ):
        """Test transcription without fallback - YouTube fails, error raised."""
        transcriber.enable_whisper_fallback = False

        from youtube_transcript_api import TranscriptsDisabled
        mock_youtube.side_effect = TranscriptsDisabled("test123")

        with pytest.raises(TranscriptsDisabled):
            transcriber.transcribe(video_id="test123", language="ru")

    def test_extract_video_id_from_url(self, transcriber):
        """Test extracting video ID from various YouTube URL formats."""
        test_cases = [
            ("https://www.youtube.com/watch?v=test123", "test123"),
            ("https://youtu.be/test456", "test456"),
            ("https://www.youtube.com/watch?v=test789&feature=share", "test789"),
            ("https://m.youtube.com/watch?v=mobile123", "mobile123"),
        ]

        for url, expected_id in test_cases:
            video_id = transcriber.extract_video_id(url)
            assert video_id == expected_id

    def test_extract_video_id_from_invalid_url(self, transcriber):
        """Test extracting video ID from invalid URL."""
        invalid_url = "https://example.com/not-youtube"

        with pytest.raises(ValueError, match="Invalid YouTube URL"):
            transcriber.extract_video_id(invalid_url)

    @patch('youtube_transcript_api.YouTubeTranscriptApi.get_transcript')
    def test_get_transcript_multiple_languages_fallback(
        self,
        mock_get_transcript,
        transcriber,
        mock_youtube_transcript
    ):
        """Test getting transcript with multiple language fallbacks."""
        from youtube_transcript_api import NoTranscriptFound

        # First language fails, second succeeds
        mock_get_transcript.side_effect = [
            NoTranscriptFound("test123", ["ru"], []),
            mock_youtube_transcript  # English succeeds
        ]

        result = transcriber.get_youtube_transcript(
            video_id="test123",
            languages=["ru", "en"]
        )

        assert result.text is not None
        assert mock_get_transcript.call_count == 2

    def test_clean_transcript_text(self, transcriber):
        """Test cleaning transcript text from artifacts."""
        dirty_text = "  Hello   world  \n\n  Test  \n"

        cleaned = transcriber.clean_transcript_text(dirty_text)

        assert cleaned == "Hello world Test"
        assert "  " not in cleaned
        assert not cleaned.startswith(" ")
        assert not cleaned.endswith(" ")

    def test_transcription_result_with_metadata(self):
        """Test TranscriptionResult with full metadata."""
        result = TranscriptionResult(
            text="Full transcript text",
            language="ru",
            source="youtube_captions",
            duration=120.5,
            word_count=150,
            has_timestamps=True
        )

        assert result.text == "Full transcript text"
        assert result.language == "ru"
        assert result.source == "youtube_captions"
        assert result.duration == 120.5
        assert result.word_count == 150
        assert result.has_timestamps is True

    @patch('youtube_transcript_api.YouTubeTranscriptApi.get_transcript')
    def test_get_transcript_with_retry_on_network_error(
        self,
        mock_get_transcript,
        transcriber,
        mock_youtube_transcript
    ):
        """Test getting transcript with retry on temporary network errors."""
        # First call fails, second succeeds
        mock_get_transcript.side_effect = [
            ConnectionError("Network error"),
            mock_youtube_transcript
        ]

        result = transcriber.get_youtube_transcript_with_retry(
            video_id="test123",
            language="ru",
            max_retries=2
        )

        assert result.text is not None
        assert mock_get_transcript.call_count == 2

    @patch('youtube_transcript_api.YouTubeTranscriptApi.get_transcript')
    def test_get_transcript_retry_exhausted(self, mock_get_transcript, transcriber):
        """Test getting transcript when all retries exhausted."""
        mock_get_transcript.side_effect = ConnectionError("Network error")

        with pytest.raises(ConnectionError):
            transcriber.get_youtube_transcript_with_retry(
                video_id="test123",
                language="ru",
                max_retries=3
            )

        assert mock_get_transcript.call_count == 3

    def test_calculate_transcript_statistics(self, transcriber, mock_youtube_transcript):
        """Test calculating statistics from transcript."""
        text = transcriber.format_transcript_to_text(mock_youtube_transcript)
        stats = transcriber.calculate_transcript_stats(text)

        assert 'word_count' in stats
        assert 'char_count' in stats
        assert 'sentence_count' in stats
        assert stats['word_count'] > 0
        assert stats['char_count'] > 0

    @pytest.mark.parametrize("language_code,expected", [
        ("ru", "ru"),
        ("en", "en"),
        ("ru-RU", "ru"),
        ("en-US", "en"),
    ])
    def test_normalize_language_code(self, transcriber, language_code, expected):
        """Test normalizing language codes to standard format."""
        normalized = transcriber.normalize_language_code(language_code)
        assert normalized == expected
