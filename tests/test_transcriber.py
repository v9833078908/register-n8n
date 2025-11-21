"""
Unit tests for AI Transcriber using Whisper API.

Tests cover:
- Audio download from YouTube
- Whisper API transcription
- Error handling
- Audio format validation
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open
from pathlib import Path
from src.ai.transcriber import Transcriber, TranscriptionResult


class TestTranscriber:
    """Test suite for Transcriber class."""

    @pytest.fixture
    def transcriber(self):
        """Create Transcriber instance for testing."""
        return Transcriber(api_key="test_api_key_123")

    @pytest.fixture
    def mock_audio_file(self, tmp_path):
        """Create mock audio file."""
        audio_file = tmp_path / "test_audio.mp3"
        audio_file.write_bytes(b"fake audio content")
        return str(audio_file)

    def test_init_with_api_key(self, transcriber):
        """Test initialization with API key."""
        assert transcriber.api_key == "test_api_key_123"

    def test_init_without_api_key(self):
        """Test initialization without API key raises ValueError."""
        with pytest.raises(ValueError, match="OpenAI API key is required"):
            Transcriber(api_key="")

    @patch('yt_dlp.YoutubeDL')
    def test_download_audio_success(self, mock_yt_dlp, transcriber, tmp_path):
        """Test successful audio download from YouTube."""
        video_url = "https://www.youtube.com/watch?v=test123"

        # Mock yt-dlp behavior
        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.return_value = {
            'id': 'test123',
            'title': 'Test Video',
            'duration': 120
        }
        mock_yt_dlp.return_value.__enter__.return_value = mock_ydl_instance

        audio_path = transcriber.download_audio(video_url, output_dir=str(tmp_path))

        assert audio_path is not None
        assert isinstance(audio_path, str)
        mock_ydl_instance.extract_info.assert_called_once_with(video_url, download=True)

    @patch('yt_dlp.YoutubeDL')
    def test_download_audio_invalid_url(self, mock_yt_dlp, transcriber):
        """Test audio download with invalid URL."""
        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.side_effect = Exception("Invalid URL")
        mock_yt_dlp.return_value.__enter__.return_value = mock_ydl_instance

        with pytest.raises(Exception, match="Invalid URL"):
            transcriber.download_audio("https://invalid-url.com")

    @patch('yt_dlp.YoutubeDL')
    def test_download_audio_network_error(self, mock_yt_dlp, transcriber):
        """Test audio download with network error."""
        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.side_effect = ConnectionError("Network error")
        mock_yt_dlp.return_value.__enter__.return_value = mock_ydl_instance

        with pytest.raises(ConnectionError):
            transcriber.download_audio("https://www.youtube.com/watch?v=test123")

    @patch('openai.OpenAI')
    def test_transcribe_audio_success(self, mock_openai, transcriber, mock_audio_file):
        """Test successful audio transcription."""
        mock_client = MagicMock()
        mock_response = Mock()
        mock_response.text = "This is the transcribed text from the audio file."
        mock_client.audio.transcriptions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        result = transcriber.transcribe_audio(mock_audio_file, language="ru")

        assert isinstance(result, TranscriptionResult)
        assert result.text == "This is the transcribed text from the audio file."
        assert result.language == "ru"
        mock_client.audio.transcriptions.create.assert_called_once()

    @patch('openai.OpenAI')
    def test_transcribe_audio_with_auto_language(self, mock_openai, transcriber, mock_audio_file):
        """Test transcription with automatic language detection."""
        mock_client = MagicMock()
        mock_response = Mock()
        mock_response.text = "Auto-detected transcription"
        mock_client.audio.transcriptions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        result = transcriber.transcribe_audio(mock_audio_file, language=None)

        assert result.text == "Auto-detected transcription"
        assert result.language is None

    @patch('openai.OpenAI')
    def test_transcribe_audio_file_not_found(self, mock_openai, transcriber):
        """Test transcription with non-existent file."""
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.side_effect = FileNotFoundError("File not found")
        mock_openai.return_value = mock_client

        with pytest.raises(FileNotFoundError):
            transcriber.transcribe_audio("/path/to/nonexistent/file.mp3")

    @patch('openai.OpenAI')
    def test_transcribe_audio_api_error(self, mock_openai, transcriber, mock_audio_file):
        """Test transcription with API error."""
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.side_effect = Exception("API Error")
        mock_openai.return_value = mock_client

        with pytest.raises(Exception, match="API Error"):
            transcriber.transcribe_audio(mock_audio_file)

    @patch('openai.OpenAI')
    def test_transcribe_audio_empty_response(self, mock_openai, transcriber, mock_audio_file):
        """Test transcription with empty response."""
        mock_client = MagicMock()
        mock_response = Mock()
        mock_response.text = ""
        mock_client.audio.transcriptions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        result = transcriber.transcribe_audio(mock_audio_file)

        assert result.text == ""

    @patch('openai.OpenAI')
    @patch.object(Transcriber, 'download_audio')
    def test_transcribe_from_youtube_url_success(
        self,
        mock_download,
        mock_openai,
        transcriber,
        mock_audio_file
    ):
        """Test full workflow from YouTube URL to transcription."""
        mock_download.return_value = mock_audio_file

        mock_client = MagicMock()
        mock_response = Mock()
        mock_response.text = "Transcribed YouTube video content"
        mock_client.audio.transcriptions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        result = transcriber.transcribe_from_youtube_url(
            "https://www.youtube.com/watch?v=test123",
            language="ru"
        )

        assert result.text == "Transcribed YouTube video content"
        mock_download.assert_called_once()

    @patch.object(Transcriber, 'download_audio')
    def test_transcribe_from_youtube_url_download_fails(self, mock_download, transcriber):
        """Test transcription when download fails."""
        mock_download.side_effect = Exception("Download failed")

        with pytest.raises(Exception, match="Download failed"):
            transcriber.transcribe_from_youtube_url("https://www.youtube.com/watch?v=test123")

    def test_validate_audio_file_exists(self, transcriber, mock_audio_file):
        """Test audio file validation for existing file."""
        assert transcriber.validate_audio_file(mock_audio_file) is True

    def test_validate_audio_file_not_exists(self, transcriber):
        """Test audio file validation for non-existent file."""
        assert transcriber.validate_audio_file("/path/to/nonexistent.mp3") is False

    def test_validate_audio_file_invalid_extension(self, transcriber, tmp_path):
        """Test audio file validation for invalid extension."""
        invalid_file = tmp_path / "test.txt"
        invalid_file.write_text("not an audio file")

        assert transcriber.validate_audio_file(str(invalid_file)) is False

    @pytest.mark.parametrize("extension", [".mp3", ".wav", ".m4a", ".ogg"])
    def test_validate_audio_file_valid_extensions(self, transcriber, tmp_path, extension):
        """Test audio file validation for valid extensions."""
        audio_file = tmp_path / f"test{extension}"
        audio_file.write_bytes(b"fake audio")

        assert transcriber.validate_audio_file(str(audio_file)) is True

    def test_transcription_result_dataclass(self):
        """Test TranscriptionResult dataclass attributes."""
        result = TranscriptionResult(
            text="Test transcription",
            language="en",
            duration=120.5
        )

        assert result.text == "Test transcription"
        assert result.language == "en"
        assert result.duration == 120.5

    @patch('openai.OpenAI')
    def test_transcribe_with_timestamps(self, mock_openai, transcriber, mock_audio_file):
        """Test transcription with timestamps."""
        mock_client = MagicMock()
        mock_response = Mock()
        mock_response.text = "Transcribed text"
        mock_response.segments = [
            {"start": 0.0, "end": 5.0, "text": "First segment"},
            {"start": 5.0, "end": 10.0, "text": "Second segment"}
        ]
        mock_client.audio.transcriptions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        result = transcriber.transcribe_audio(mock_audio_file, include_timestamps=True)

        assert result.text == "Transcribed text"
        assert hasattr(result, 'segments')

    def test_cleanup_audio_file(self, transcriber, mock_audio_file):
        """Test cleanup of downloaded audio file."""
        assert Path(mock_audio_file).exists()

        transcriber.cleanup_audio_file(mock_audio_file)

        assert not Path(mock_audio_file).exists()

    def test_cleanup_audio_file_not_exists(self, transcriber):
        """Test cleanup of non-existent file doesn't raise error."""
        # Should not raise exception
        transcriber.cleanup_audio_file("/path/to/nonexistent.mp3")
