"""
Content Moderator for quality validation.

Validates transcripts and posts for content quality (length, spam, repetition).
"""
import re
import yaml
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Any


class SafetyLevel(str, Enum):
    """Safety level for content."""
    SAFE = "safe"
    WARNING = "warning"
    UNSAFE = "unsafe"


@dataclass
class Violation:
    """Violation dataclass."""
    type: str
    message: str
    severity: int = 5

    def __str__(self) -> str:
        """Return message for string representation."""
        return self.message

    def lower(self) -> str:
        """Return lowercase message for string comparisons."""
        return self.message.lower()


@dataclass
class ModerationResult:
    """Result of content moderation."""
    is_safe: bool
    safety_level: SafetyLevel
    violations: List[Violation] = field(default_factory=list)
    length_valid: bool = True
    word_count: Optional[int] = None
    reason: str = ""


class Moderator:
    """Content moderator for quality validation."""

    def __init__(
        self,
        config_path: Optional[str] = None,
        testing_mode: bool = False
    ):
        """
        Initialize Moderator.

        Args:
            config_path: Path to guardrails config file
            testing_mode: Use less strict validation for testing
        """
        self.config_path = config_path
        self.testing_mode = testing_mode

        # Load configuration
        self.config = self.load_config() if config_path else self._get_default_config()

        # Apply testing mode overrides
        if testing_mode and 'test_mode_settings' in self.config:
            test_settings = self.config['test_mode_settings']
            self.min_length = test_settings.get('min_length', 10)
            self.min_word_count = test_settings.get('min_word_count', 3)
            self.block_threshold = test_settings.get('block_threshold', 15)
        else:
            # Production settings
            transcript_val = self.config.get('transcript_validation', {})
            self.min_length = transcript_val.get('min_length', 100)
            self.max_length = transcript_val.get('max_length', 50000)
            self.min_word_count = transcript_val.get('min_word_count', 20)
            self.max_word_count = transcript_val.get('max_word_count', 10000)
            self.max_repetition_ratio = transcript_val.get('max_repetition_ratio', 0.5)
            self.min_alpha_ratio = transcript_val.get('min_alpha_ratio', 0.5)

            moderation = self.config.get('moderation', {})
            self.block_threshold = moderation.get('block_threshold', 8)
            self.warning_threshold = moderation.get('warning_threshold', 5)

        # Platform limits
        post_val = self.config.get('post_validation', {})
        self.platform_limits = post_val.get('platform_limits', {
            'threads': {'max_length': 500, 'min_length': 20, 'max_hashtags': 5, 'max_emojis': 10}
        })

        # Spam patterns
        quality_checks = post_val.get('quality_checks', {})
        self.spam_patterns = quality_checks.get('spam_patterns', [])

    def load_config(self) -> Dict[str, Any]:
        """
        Load configuration from YAML file.

        Returns:
            Configuration dictionary
        """
        if not self.config_path:
            return self._get_default_config()

        config_file = Path(self.config_path)
        if not config_file.exists():
            return self._get_default_config()

        with open(config_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            'transcript_validation': {
                'min_length': 100,
                'max_length': 50000,
                'min_word_count': 20,
                'max_word_count': 10000,
                'max_repetition_ratio': 0.5,
                'min_alpha_ratio': 0.5
            },
            'post_validation': {
                'platform_limits': {
                    'threads': {
                        'max_length': 500,
                        'min_length': 20,
                        'max_hashtags': 5,
                        'max_emojis': 10
                    }
                },
                'quality_checks': {
                    'spam_patterns': [
                        r'!{3,}',
                        r'[А-ЯA-Z]{20,}',
                        r'(.)\1{10,}'
                    ]
                }
            },
            'moderation': {
                'block_threshold': 8,
                'warning_threshold': 5
            }
        }

    def check_transcript(self, transcript: str) -> ModerationResult:
        """
        Check transcript for quality issues.

        Args:
            transcript: Transcript text

        Returns:
            ModerationResult object
        """
        violations = []

        # Check length
        if len(transcript) < self.min_length:
            violations.append(Violation(
                type="too_short",
                message="Transcript too short"
            ))

        if len(transcript) > self.max_length:
            violations.append(Violation(
                type="too_long",
                message="Transcript too long"
            ))

        # Check word count
        word_count = self.calculate_word_count(transcript)
        if word_count < self.min_word_count:
            violations.append(Violation(
                type="too_short",
                message=f"Insufficient word count: {word_count} (min: {self.min_word_count})"
            ))

        # Check for repetitive content
        if self.check_repetition(transcript):
            violations.append(Violation(
                type="repetitive_content",
                message="Content is too repetitive"
            ))

        # Check alpha ratio
        alpha_ratio = self.calculate_alpha_ratio(transcript)
        if alpha_ratio < self.min_alpha_ratio:
            violations.append(Violation(
                type="insufficient_alpha",
                message=f"Insufficient letter content (alpha ratio: {alpha_ratio:.2f})"
            ))

        # Determine safety level
        is_safe = len(violations) == 0
        if is_safe:
            safety_level = SafetyLevel.SAFE
        elif len(violations) <= 2:
            safety_level = SafetyLevel.WARNING
        else:
            safety_level = SafetyLevel.UNSAFE

        return ModerationResult(
            is_safe=is_safe,
            safety_level=safety_level,
            violations=violations,
            length_valid=self.min_length <= len(transcript) <= self.max_length,
            word_count=word_count,
            reason="; ".join(str(v) for v in violations) if violations else "Content is valid"
        )

    def check_post(self, post: str, platform: str = 'threads') -> ModerationResult:
        """
        Check post for quality issues.

        Args:
            post: Post text
            platform: Platform name

        Returns:
            ModerationResult object
        """
        violations = []

        # Get platform limits
        limits = self.platform_limits.get(platform, {})
        min_len = limits.get('min_length', 20)
        max_len = limits.get('max_length', 500)
        max_hashtags = limits.get('max_hashtags', 5)
        max_emojis = limits.get('max_emojis', 10)

        # Check length
        length_valid = min_len <= len(post) <= max_len
        if len(post) < min_len:
            violations.append(Violation(
                type="too_short",
                message=f"Post too short: {len(post)} chars (min: {min_len})"
            ))

        if len(post) > max_len:
            violations.append(Violation(
                type="length_exceeded",
                message=f"Post too long: {len(post)} chars (max: {max_len})"
            ))

        # Check for spam patterns
        if self.check_spam_patterns(post):
            violations.append(Violation(
                type="spam_detected",
                message="Spam pattern detected"
            ))

        # Check hashtag count
        hashtag_count = self.count_hashtags(post)
        if hashtag_count > max_hashtags:
            violations.append(Violation(
                type="excessive_hashtags",
                message=f"Too many hashtags: {hashtag_count} (max: {max_hashtags})"
            ))

        # Check emoji count
        emoji_count = self.count_emojis(post)
        if emoji_count >= max_emojis:
            violations.append(Violation(
                type="excessive_emojis",
                message=f"Too many emojis: {emoji_count} (max: {max_emojis})"
            ))

        # Determine safety
        is_safe = len(violations) == 0
        if is_safe:
            safety_level = SafetyLevel.SAFE
        elif len(violations) <= 2:
            safety_level = SafetyLevel.WARNING
        else:
            safety_level = SafetyLevel.UNSAFE

        return ModerationResult(
            is_safe=is_safe,
            safety_level=safety_level,
            violations=violations,
            length_valid=length_valid,
            word_count=self.calculate_word_count(post),
            reason="; ".join(str(v) for v in violations) if violations else "Post is valid"
        )

    def calculate_word_count(self, text: str) -> int:
        """
        Calculate word count.

        Args:
            text: Text to analyze

        Returns:
            Word count
        """
        if not text:
            return 0
        return len(text.split())

    def check_repetition(self, text: str) -> bool:
        """
        Check for repetitive content.

        Args:
            text: Text to analyze

        Returns:
            True if content is too repetitive
        """
        if not text or len(text) < 50:
            return False

        words = text.lower().split()
        if len(words) < 10:
            return False

        # Count unique words
        unique_words = set(words)
        repetition_ratio = 1 - (len(unique_words) / len(words))

        return repetition_ratio > self.max_repetition_ratio

    def calculate_alpha_ratio(self, text: str) -> float:
        """
        Calculate ratio of alphabetic characters.

        Args:
            text: Text to analyze

        Returns:
            Ratio (0.0 to 1.0)
        """
        if not text:
            return 0.0

        alpha_count = sum(c.isalpha() for c in text)
        return alpha_count / len(text)

    def detect_language(self, text: str) -> str:
        """
        Detect language of text.

        Args:
            text: Text to analyze

        Returns:
            Language code or "unknown"
        """
        # Simple heuristic: check for Cyrillic characters
        cyrillic_count = sum(1 for c in text if '\u0400' <= c <= '\u04FF')
        latin_count = sum(1 for c in text if c.isalpha() and not ('\u0400' <= c <= '\u04FF'))

        if cyrillic_count > latin_count:
            return "ru"
        elif latin_count > cyrillic_count:
            return "en"

        return "unknown"

    def check_spam_patterns(self, text: str) -> bool:
        """
        Check for spam patterns.

        Args:
            text: Text to analyze

        Returns:
            True if spam detected
        """
        for pattern in self.spam_patterns:
            if re.search(pattern, text):
                return True
        return False

    def count_hashtags(self, text: str) -> int:
        """
        Count hashtags in text.

        Args:
            text: Text to analyze

        Returns:
            Hashtag count
        """
        return len(re.findall(r'#\w+', text))

    def count_emojis(self, text: str) -> int:
        """
        Count emojis in text.

        Args:
            text: Text to analyze

        Returns:
            Emoji count
        """
        # Unicode emoji ranges
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map
            "\U0001F1E0-\U0001F1FF"  # flags
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+",
            flags=re.UNICODE
        )
        return len(emoji_pattern.findall(text))

    def validate_length(
        self,
        content: str,
        platform: Optional[str] = None,
        content_type: str = 'post'
    ) -> bool:
        """
        Validate content length.

        Args:
            content: Content to validate
            platform: Platform name (for posts)
            content_type: 'post' or 'transcript'

        Returns:
            True if length is valid
        """
        if content_type == 'transcript':
            return self.min_length <= len(content) <= self.max_length

        # Post validation
        if platform and platform in self.platform_limits:
            limits = self.platform_limits[platform]
            min_len = limits.get('min_length', 20)
            max_len = limits.get('max_length', 500)
            return min_len <= len(content) <= max_len

        return True

    def validate_content(
        self,
        content: str,
        content_type: str = 'transcript',
        platform: Optional[str] = None
    ) -> ModerationResult:
        """
        Validate content (unified method).

        Args:
            content: Content to validate
            content_type: 'transcript' or 'post'
            platform: Platform name (for posts)

        Returns:
            ModerationResult object
        """
        if content_type == 'transcript':
            return self.check_transcript(content)
        else:
            return self.check_post(content, platform=platform or 'threads')

    def auto_fix(self, post: str, platform: str = 'threads') -> str:
        """
        Auto-fix minor issues in post.

        Args:
            post: Post text
            platform: Platform name

        Returns:
            Fixed post text
        """
        # Get max length
        limits = self.platform_limits.get(platform, {})
        max_len = limits.get('max_length', 500)

        # Truncate if too long
        if len(post) > max_len:
            post = post[:max_len - 3] + "..."

        # Fix whitespace
        post = self.auto_fix_whitespace(post)

        return post

    def auto_fix_whitespace(self, text: str) -> str:
        """
        Fix excessive whitespace.

        Args:
            text: Text to fix

        Returns:
            Fixed text
        """
        # Replace multiple spaces with single space
        text = re.sub(r' +', ' ', text)
        # Remove leading/trailing whitespace
        text = text.strip()
        return text

    def calculate_severity_score(self, violations: List[Dict[str, Any]]) -> int:
        """
        Calculate severity score for violations.

        Args:
            violations: List of violation dictionaries

        Returns:
            Total severity score
        """
        severity_weights = self.config.get('severity_weights', {
            'too_short': 8,
            'too_long': 5,
            'repetitive_content': 7,
            'spam_detected': 9,
            'insufficient_alpha': 6
        })

        total_score = 0
        for violation in violations:
            vtype = violation.get('type', 'unknown')
            total_score += severity_weights.get(vtype, 5)

        return total_score

    def generate_report(self, result: ModerationResult) -> Dict[str, Any]:
        """
        Generate detailed moderation report.

        Args:
            result: ModerationResult object

        Returns:
            Report dictionary
        """
        return {
            'safety_level': result.safety_level.value,
            'is_safe': result.is_safe,
            'violations': result.violations,
            'statistics': {
                'word_count': result.word_count,
                'length_valid': result.length_valid
            },
            'reason': result.reason
        }

    def validate_hashtag_length(self, hashtag: str) -> bool:
        """
        Validate hashtag length.

        Args:
            hashtag: Hashtag text (including #)

        Returns:
            True if valid length
        """
        quality_checks = self.config.get('post_validation', {}).get('quality_checks', {})
        max_hashtag_len = quality_checks.get('max_hashtag_length', 30)

        # Remove # and check length
        tag_text = hashtag.lstrip('#')
        return len(tag_text) <= max_hashtag_len

    def get_statistics(self, text: str) -> Dict[str, Any]:
        """
        Get content statistics.

        Args:
            text: Text to analyze

        Returns:
            Statistics dictionary
        """
        return {
            'char_count': len(text),
            'word_count': self.calculate_word_count(text),
            'alpha_ratio': self.calculate_alpha_ratio(text),
            'line_count': text.count('\n') + 1 if text else 0
        }
