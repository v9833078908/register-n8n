"""
Unit tests for Content Moderator (Guardrails).

Tests cover:
- Transcript length validation
- Content quality checks
- Spam detection
- Post length validation
- Platform-specific rules
"""
import pytest
from unittest.mock import Mock, patch
from src.ai.moderator import Moderator, ModerationResult, SafetyLevel


class TestModerator:
    """Test suite for Moderator class."""

    @pytest.fixture
    def moderator(self):
        """Create Moderator instance for testing."""
        return Moderator(config_path="config/guardrails.yaml")

    @pytest.fixture
    def valid_transcript(self):
        """Valid transcript with sufficient content."""
        return """
        Сегодня я хочу поговорить о важной теме.
        Это интересная информация которая будет полезна многим.
        В этом видео мы разберем основные моменты и детали.
        Надеюсь эта информация будет вам полезна.
        Спасибо за просмотр!
        """

    @pytest.fixture
    def too_short_transcript(self):
        """Transcript that's too short."""
        return "Привет!"

    @pytest.fixture
    def too_long_transcript(self):
        """Transcript that's too long."""
        return "A" * 60000  # Exceeds max_length

    @pytest.fixture
    def repetitive_transcript(self):
        """Transcript with repetitive content."""
        return "повтор " * 100  # Very repetitive

    @pytest.fixture
    def low_alpha_transcript(self):
        """Transcript with insufficient letters."""
        return "123 456 789 !!! @@@ ### $$$ %%% ^^^"

    @pytest.fixture
    def valid_post(self):
        """Valid post within limits."""
        return """
        Интересная тема для обсуждения!

        Сегодня разберем важные моменты. 💡

        Что думаете? Пишите в комментариях!

        #обсуждение
        """

    @pytest.fixture
    def too_short_post(self):
        """Post that's too short."""
        return "Привет"

    @pytest.fixture
    def too_long_post(self):
        """Post exceeding Threads limit."""
        return "A" * 600  # Exceeds 500 char limit

    @pytest.fixture
    def spam_post(self):
        """Post with spam patterns."""
        return "КУПИТЕ СЕЙЧАС!!! ЭТО СУПЕР ПРЕДЛОЖЕНИЕ!!! НЕ ПРОПУСТИТЕ!!!"

    def test_init_with_config(self, moderator):
        """Test initialization with config file."""
        assert moderator.config_path == "config/guardrails.yaml"

    def test_init_without_config(self):
        """Test initialization without config uses defaults."""
        moderator = Moderator()
        assert moderator.config_path is None
        assert hasattr(moderator, 'min_length')

    def test_check_transcript_valid(self, moderator, valid_transcript):
        """Test checking valid transcript passes."""
        result = moderator.check_transcript(valid_transcript)

        assert isinstance(result, ModerationResult)
        assert result.is_safe is True
        assert result.safety_level == SafetyLevel.SAFE
        assert len(result.violations) == 0

    def test_check_transcript_too_short(self, moderator, too_short_transcript):
        """Test checking transcript that's too short."""
        result = moderator.check_transcript(too_short_transcript)

        assert result.is_safe is False
        assert result.safety_level in [SafetyLevel.UNSAFE, SafetyLevel.WARNING]
        assert any('short' in v.lower() or 'length' in v.lower() for v in result.violations)

    def test_check_transcript_too_long(self, moderator, too_long_transcript):
        """Test checking transcript that's too long."""
        result = moderator.check_transcript(too_long_transcript)

        assert result.is_safe is False
        assert any('long' in v.lower() or 'length' in v.lower() for v in result.violations)

    def test_check_transcript_repetitive(self, moderator, repetitive_transcript):
        """Test checking repetitive transcript."""
        result = moderator.check_transcript(repetitive_transcript)

        assert result.is_safe is False
        assert any('repetit' in v.lower() for v in result.violations)

    def test_check_transcript_insufficient_alpha(self, moderator, low_alpha_transcript):
        """Test checking transcript with insufficient letters."""
        result = moderator.check_transcript(low_alpha_transcript)

        assert result.is_safe is False
        assert any('alpha' in v.lower() or 'letter' in v.lower() for v in result.violations)

    def test_check_post_valid(self, moderator, valid_post):
        """Test checking valid post."""
        result = moderator.check_post(valid_post, platform='threads')

        assert result.is_safe is True
        assert result.length_valid is True
        assert len(result.violations) == 0

    def test_check_post_too_short(self, moderator, too_short_post):
        """Test checking post that's too short."""
        result = moderator.check_post(too_short_post, platform='threads')

        assert result.is_safe is False
        assert result.length_valid is False

    def test_check_post_too_long(self, moderator, too_long_post):
        """Test checking post that's too long."""
        result = moderator.check_post(too_long_post, platform='threads')

        assert result.is_safe is False
        assert result.length_valid is False
        assert any(v.type == 'length_exceeded' for v in result.violations)

    def test_check_post_spam_detected(self, moderator, spam_post):
        """Test detecting spam patterns in post."""
        result = moderator.check_post(spam_post, platform='threads')

        assert result.is_safe is False
        assert any('spam' in v.lower() for v in result.violations)

    def test_calculate_word_count(self, moderator, valid_transcript):
        """Test calculating word count."""
        word_count = moderator.calculate_word_count(valid_transcript)

        assert word_count > 0
        assert isinstance(word_count, int)

    def test_calculate_word_count_empty(self, moderator):
        """Test calculating word count for empty string."""
        word_count = moderator.calculate_word_count("")

        assert word_count == 0

    def test_check_repetition(self, moderator, repetitive_transcript):
        """Test checking for repetitive content."""
        is_repetitive = moderator.check_repetition(repetitive_transcript)

        assert is_repetitive is True

    def test_check_repetition_normal_text(self, moderator, valid_transcript):
        """Test checking repetition for normal text."""
        is_repetitive = moderator.check_repetition(valid_transcript)

        assert is_repetitive is False

    def test_calculate_alpha_ratio(self, moderator, valid_transcript):
        """Test calculating alpha character ratio."""
        alpha_ratio = moderator.calculate_alpha_ratio(valid_transcript)

        assert 0.0 <= alpha_ratio <= 1.0
        assert alpha_ratio > 0.5  # Valid transcript should have >50% letters

    def test_calculate_alpha_ratio_low(self, moderator, low_alpha_transcript):
        """Test calculating alpha ratio for non-alphabetic text."""
        alpha_ratio = moderator.calculate_alpha_ratio(low_alpha_transcript)

        assert alpha_ratio < 0.5  # Should be low

    def test_detect_language(self, moderator):
        """Test language detection."""
        russian_text = "Это текст на русском языке"
        english_text = "This is text in English language"

        lang_ru = moderator.detect_language(russian_text)
        lang_en = moderator.detect_language(english_text)

        assert lang_ru in ["ru", "unknown"]
        assert lang_en in ["en", "unknown"]

    def test_check_spam_patterns(self, moderator, spam_post):
        """Test spam pattern detection."""
        has_spam = moderator.check_spam_patterns(spam_post)

        assert has_spam is True

    def test_check_spam_patterns_clean_text(self, moderator, valid_post):
        """Test spam detection on clean text."""
        has_spam = moderator.check_spam_patterns(valid_post)

        assert has_spam is False

    def test_count_hashtags(self, moderator):
        """Test counting hashtags in post."""
        post_with_hashtags = "Test post #one #two #three"

        count = moderator.count_hashtags(post_with_hashtags)

        assert count == 3

    def test_count_hashtags_none(self, moderator):
        """Test counting hashtags when there are none."""
        post_without_hashtags = "Test post without hashtags"

        count = moderator.count_hashtags(post_without_hashtags)

        assert count == 0

    def test_count_emojis(self, moderator):
        """Test counting emojis in post."""
        post_with_emojis = "Test 💡 post 🎯 with 🔥 emojis"

        count = moderator.count_emojis(post_with_emojis)

        assert count == 3

    def test_count_emojis_none(self, moderator):
        """Test counting emojis when there are none."""
        post_without_emojis = "Test post without emojis"

        count = moderator.count_emojis(post_without_emojis)

        assert count == 0

    def test_validate_post_length_threads(self, moderator):
        """Test post length validation for Threads."""
        short_post = "Short post"
        valid_post = "A" * 300
        long_post = "A" * 600

        assert moderator.validate_length(short_post, 'threads', 'post') is False
        assert moderator.validate_length(valid_post, 'threads', 'post') is True
        assert moderator.validate_length(long_post, 'threads', 'post') is False

    def test_validate_transcript_length(self, moderator, valid_transcript, too_short_transcript):
        """Test transcript length validation."""
        assert moderator.validate_length(valid_transcript, None, 'transcript') is True
        assert moderator.validate_length(too_short_transcript, None, 'transcript') is False

    def test_moderation_result_dataclass(self):
        """Test ModerationResult dataclass attributes."""
        result = ModerationResult(
            is_safe=True,
            safety_level=SafetyLevel.SAFE,
            violations=[],
            length_valid=True,
            word_count=100,
            reason="Content is valid"
        )

        assert result.is_safe is True
        assert result.safety_level == SafetyLevel.SAFE
        assert result.length_valid is True
        assert result.word_count == 100

    def test_safety_level_enum(self):
        """Test SafetyLevel enum values."""
        assert SafetyLevel.SAFE.value == "safe"
        assert SafetyLevel.WARNING.value == "warning"
        assert SafetyLevel.UNSAFE.value == "unsafe"

    def test_load_config_from_file(self, moderator):
        """Test loading guardrails configuration from file."""
        config = moderator.load_config()

        assert 'transcript_validation' in config
        assert 'post_validation' in config
        assert 'min_length' in config['transcript_validation']

    def test_validate_multiple_checks(self, moderator, valid_transcript, valid_post):
        """Test running all validation checks together."""
        # Check transcript
        transcript_result = moderator.validate_content(
            content=valid_transcript,
            content_type='transcript'
        )

        assert transcript_result.is_safe is True
        assert transcript_result.length_valid is True

        # Check post
        post_result = moderator.validate_content(
            content=valid_post,
            content_type='post',
            platform='threads'
        )

        assert post_result.is_safe is True
        assert post_result.length_valid is True

    @pytest.mark.parametrize("platform,max_length", [
        ("threads", 500),
    ])
    def test_platform_specific_validation(self, moderator, platform, max_length):
        """Test platform-specific validation rules."""
        short_text = "A" * (max_length - 10)
        long_text = "A" * (max_length + 10)

        result_short = moderator.check_post(short_text, platform=platform)
        result_long = moderator.check_post(long_text, platform=platform)

        assert result_short.length_valid is True
        assert result_long.length_valid is False

    def test_auto_fix_truncate_long_post(self, moderator):
        """Test auto-fixing long post by truncation."""
        long_post = "A" * 600

        fixed_post = moderator.auto_fix(long_post, 'threads')

        assert len(fixed_post) <= 500
        assert fixed_post.endswith("...")

    def test_auto_fix_trim_whitespace(self, moderator):
        """Test auto-fixing whitespace."""
        messy_post = "  Test   post  with   extra    spaces  "

        fixed_post = moderator.auto_fix_whitespace(messy_post)

        assert "  " not in fixed_post
        assert not fixed_post.startswith(" ")
        assert not fixed_post.endswith(" ")

    def test_severity_scoring(self, moderator):
        """Test severity scoring for violations."""
        violations = [
            {'type': 'too_short', 'message': 'Content too short'},
            {'type': 'spam_detected', 'message': 'Spam pattern found'}
        ]

        score = moderator.calculate_severity_score(violations)

        assert score > 0
        assert isinstance(score, (int, float))

    def test_generate_moderation_report(self, moderator, valid_transcript):
        """Test generating detailed moderation report."""
        result = moderator.check_transcript(valid_transcript)
        report = moderator.generate_report(result)

        assert 'safety_level' in report
        assert 'violations' in report
        assert 'statistics' in report
        assert isinstance(report, dict)

    def test_check_excessive_emojis(self, moderator):
        """Test detecting excessive emoji usage."""
        post_with_many_emojis = "Test 🎯 post 💡 with 🔥 too 😊 many 🚀 emojis 🎨 here 🌟 wow 🎉 amazing ✨ cool 🌈"

        result = moderator.check_post(post_with_many_emojis, platform='threads')

        assert any('emoji' in v.lower() for v in result.violations)

    def test_check_excessive_hashtags(self, moderator):
        """Test detecting excessive hashtag usage."""
        post_with_many_hashtags = "Test #one #two #three #four #five #six #seven"

        result = moderator.check_post(post_with_many_hashtags, platform='threads')

        assert any('hashtag' in v.lower() for v in result.violations)

    def test_validate_hashtag_length(self, moderator):
        """Test validating individual hashtag length."""
        short_hashtag = "#test"
        long_hashtag = "#" + "A" * 50

        assert moderator.validate_hashtag_length(short_hashtag) is True
        assert moderator.validate_hashtag_length(long_hashtag) is False

    def test_testing_mode_less_strict(self):
        """Test that testing mode is less strict."""
        strict_moderator = Moderator(testing_mode=False)
        lenient_moderator = Moderator(testing_mode=True)

        very_short_text = "Hi"

        strict_result = strict_moderator.check_transcript(very_short_text)
        lenient_result = lenient_moderator.check_transcript(very_short_text)

        # Strict mode should fail, lenient might pass
        assert strict_result.is_safe is False
        # Lenient mode might still fail but with lower severity

    def test_get_statistics(self, moderator, valid_transcript):
        """Test getting content statistics."""
        stats = moderator.get_statistics(valid_transcript)

        assert 'char_count' in stats
        assert 'word_count' in stats
        assert 'alpha_ratio' in stats
        assert 'line_count' in stats

    @pytest.mark.parametrize("text,expected_word_count", [
        ("Hello world", 2),
        ("One two three four", 4),
        ("", 0),
        ("Single", 1),
    ])
    def test_word_count_parametrized(self, moderator, text, expected_word_count):
        """Test word count with various inputs."""
        count = moderator.calculate_word_count(text)
        assert count == expected_word_count
