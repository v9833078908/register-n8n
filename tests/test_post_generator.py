"""
Unit tests for AI Post Generator using Claude API.

Tests cover:
- Post generation from transcript
- Platform-specific formatting (Threads)
- Prompt loading and management
- Error handling
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open
from src.ai.post_generator import PostGenerator, GeneratedPost


class TestPostGenerator:
    """Test suite for PostGenerator class."""

    @pytest.fixture
    def generator(self):
        """Create PostGenerator instance for testing."""
        return PostGenerator(api_key="test_anthropic_key_123")

    @pytest.fixture
    def sample_transcript(self):
        """Sample transcript for testing."""
        return """
        Сегодня я хочу поговорить о важности витамина D для здоровья.
        Многие люди не знают, что дефицит витамина D очень распространен,
        особенно в зимние месяцы. Витамин D играет ключевую роль в иммунной
        системе и здоровье костей. Важно проконсультироваться с врачом
        перед началом приема любых добавок.
        """

    @pytest.fixture
    def sample_video_metadata(self):
        """Sample video metadata for testing."""
        return {
            'title': 'Важность витамина D для здоровья',
            'duration': 180,
            'video_type': 'short',
            'url': 'https://www.youtube.com/watch?v=test123'
        }

    @pytest.fixture
    def mock_prompt_config(self):
        """Mock prompt configuration."""
        return {
            'threads': {
                'system': 'You are a medical content expert for Threads.',
                'user_template': 'Create a Threads post based on: {transcript}'
            }
        }

    def test_init_with_api_key(self, generator):
        """Test initialization with API key."""
        assert generator.api_key == "test_anthropic_key_123"

    def test_init_without_api_key(self):
        """Test initialization without API key raises ValueError."""
        with pytest.raises(ValueError, match="Anthropic API key is required"):
            PostGenerator(api_key="")

    @patch('builtins.open', new_callable=mock_open, read_data='system: Test prompt\nuser_template: Create post from {transcript}')
    def test_load_prompt_from_file(self, mock_file, generator):
        """Test loading prompt from file."""
        prompt_config = generator.load_prompt_from_file('threads')

        assert 'system' in prompt_config
        assert 'user_template' in prompt_config

    def test_load_prompt_file_not_found(self, generator):
        """Test loading prompt from non-existent file."""
        with pytest.raises(FileNotFoundError):
            generator.load_prompt_from_file('nonexistent_platform')

    @patch('anthropic.Anthropic')
    def test_generate_post_success(
        self,
        mock_anthropic,
        generator,
        sample_transcript,
        sample_video_metadata
    ):
        """Test successful post generation."""
        mock_client = MagicMock()
        mock_response = Mock()
        mock_response.content = [Mock(text="🩺 Витамин D - ключ к здоровью!\n\nОсобенно важен зимой для иммунитета и костей.\n\n⚠️ Это общая информация, не медицинская рекомендация. Проконсультируйтесь с врачом!\n\n#здоровье #витаминD")]
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        post = generator.generate_post(
            transcript=sample_transcript,
            platform='threads',
            video_metadata=sample_video_metadata
        )

        assert isinstance(post, GeneratedPost)
        assert post.platform == 'threads'
        assert len(post.content) > 0
        assert "витамин" in post.content.lower()
        mock_client.messages.create.assert_called_once()

    @patch('anthropic.Anthropic')
    def test_generate_post_api_error(
        self,
        mock_anthropic,
        generator,
        sample_transcript,
        sample_video_metadata
    ):
        """Test post generation with API error."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API Error")
        mock_anthropic.return_value = mock_client

        with pytest.raises(Exception, match="API Error"):
            generator.generate_post(
                transcript=sample_transcript,
                platform='threads',
                video_metadata=sample_video_metadata
            )

    @patch('anthropic.Anthropic')
    def test_generate_post_empty_transcript(self, mock_anthropic, generator, sample_video_metadata):
        """Test post generation with empty transcript."""
        with pytest.raises(ValueError, match="Transcript cannot be empty"):
            generator.generate_post(
                transcript="",
                platform='threads',
                video_metadata=sample_video_metadata
            )

    @patch('anthropic.Anthropic')
    def test_generate_post_unsupported_platform(
        self,
        mock_anthropic,
        generator,
        sample_transcript,
        sample_video_metadata
    ):
        """Test post generation for unsupported platform."""
        with pytest.raises(ValueError, match="Unsupported platform"):
            generator.generate_post(
                transcript=sample_transcript,
                platform='unsupported_platform',
                video_metadata=sample_video_metadata
            )

    @patch('anthropic.Anthropic')
    def test_generate_post_with_custom_instructions(
        self,
        mock_anthropic,
        generator,
        sample_transcript,
        sample_video_metadata
    ):
        """Test post generation with custom instructions."""
        mock_client = MagicMock()
        mock_response = Mock()
        mock_response.content = [Mock(text="Custom styled post")]
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        custom_instructions = "Write in a very casual, friendly tone"
        post = generator.generate_post(
            transcript=sample_transcript,
            platform='threads',
            video_metadata=sample_video_metadata,
            custom_instructions=custom_instructions
        )

        assert isinstance(post, GeneratedPost)
        # Verify custom instructions were passed to API
        call_args = mock_client.messages.create.call_args
        assert custom_instructions in str(call_args)

    def test_format_prompt_with_metadata(self, generator, sample_transcript, sample_video_metadata):
        """Test prompt formatting with video metadata."""
        template = "Title: {title}\nDuration: {duration}\nTranscript: {transcript}"

        formatted = generator.format_prompt(
            template=template,
            transcript=sample_transcript,
            video_metadata=sample_video_metadata
        )

        assert sample_video_metadata['title'] in formatted
        assert str(sample_video_metadata['duration']) in formatted
        assert sample_transcript in formatted

    def test_validate_post_length_threads(self, generator):
        """Test post length validation for Threads (500 char limit)."""
        short_post = "This is a short post" * 10  # Less than 500 chars
        long_post = "This is a very long post " * 50  # More than 500 chars

        assert generator.validate_post_length(short_post, 'threads') is True
        assert generator.validate_post_length(long_post, 'threads') is False

    def test_validate_post_length_invalid_platform(self, generator):
        """Test post length validation for invalid platform."""
        with pytest.raises(ValueError, match="Unknown platform"):
            generator.validate_post_length("Test post", 'invalid_platform')

    def test_extract_hashtags_from_post(self, generator):
        """Test extracting hashtags from generated post."""
        post_with_hashtags = "Test post about health #здоровье #витаминD #медицина"

        hashtags = generator.extract_hashtags(post_with_hashtags)

        assert len(hashtags) == 3
        assert '#здоровье' in hashtags
        assert '#витаминD' in hashtags
        assert '#медицина' in hashtags

    def test_extract_hashtags_no_hashtags(self, generator):
        """Test extracting hashtags from post without hashtags."""
        post_without_hashtags = "Test post about health without hashtags"

        hashtags = generator.extract_hashtags(post_without_hashtags)

        assert len(hashtags) == 0

    def test_count_emojis_in_post(self, generator):
        """Test counting emojis in post."""
        post_with_emojis = "🩺 Health post 💊 with emojis 🏥"

        emoji_count = generator.count_emojis(post_with_emojis)

        assert emoji_count == 3

    def test_count_emojis_no_emojis(self, generator):
        """Test counting emojis in post without emojis."""
        post_without_emojis = "Health post without emojis"

        emoji_count = generator.count_emojis(post_without_emojis)

        assert emoji_count == 0

    def test_generated_post_dataclass(self):
        """Test GeneratedPost dataclass attributes."""
        post = GeneratedPost(
            platform='threads',
            content='Test post content',
            hashtags=['#test', '#health'],
            emoji_count=2,
            char_count=100
        )

        assert post.platform == 'threads'
        assert post.content == 'Test post content'
        assert post.hashtags == ['#test', '#health']
        assert post.emoji_count == 2
        assert post.char_count == 100

    @patch('anthropic.Anthropic')
    def test_generate_post_rate_limit_error(
        self,
        mock_anthropic,
        generator,
        sample_transcript,
        sample_video_metadata
    ):
        """Test handling of rate limit errors."""
        mock_client = MagicMock()
        from anthropic import RateLimitError
        mock_client.messages.create.side_effect = RateLimitError("Rate limit exceeded")
        mock_anthropic.return_value = mock_client

        with pytest.raises(RateLimitError):
            generator.generate_post(
                transcript=sample_transcript,
                platform='threads',
                video_metadata=sample_video_metadata
            )

    @patch('anthropic.Anthropic')
    def test_generate_post_with_retry_logic(
        self,
        mock_anthropic,
        generator,
        sample_transcript,
        sample_video_metadata
    ):
        """Test post generation with retry logic on failure."""
        mock_client = MagicMock()

        # First call fails, second succeeds
        mock_response = Mock()
        mock_response.content = [Mock(text="Success after retry")]
        mock_client.messages.create.side_effect = [
            Exception("Temporary error"),
            mock_response
        ]
        mock_anthropic.return_value = mock_client

        post = generator.generate_post_with_retry(
            transcript=sample_transcript,
            platform='threads',
            video_metadata=sample_video_metadata,
            max_retries=2
        )

        assert post.content == "Success after retry"
        assert mock_client.messages.create.call_count == 2

    def test_truncate_post_if_too_long(self, generator):
        """Test truncating post if it exceeds platform limit."""
        long_post = "A" * 600  # Exceeds Threads 500 char limit

        truncated = generator.truncate_post(long_post, 'threads')

        assert len(truncated) <= 500
        assert truncated.endswith("...")

    @pytest.mark.parametrize("platform,max_length", [
        ("threads", 500),
    ])
    def test_platform_character_limits(self, generator, platform, max_length):
        """Test character limits for different platforms."""
        limits = generator.get_platform_limits()

        assert limits[platform]['max_length'] == max_length
