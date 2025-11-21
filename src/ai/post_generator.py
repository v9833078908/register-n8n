"""
AI Post Generator using Claude API.

Generates platform-specific social media posts from YouTube video transcripts.
"""
import re
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any
import time

import anthropic


@dataclass
class GeneratedPost:
    """Dataclass for generated post."""
    platform: str
    content: str
    hashtags: List[str] = field(default_factory=list)
    emoji_count: int = 0
    char_count: int = 0


class PostGenerator:
    """Post generator using Claude API."""

    # Platform limits
    PLATFORM_LIMITS = {
        'threads': {
            'max_length': 500,
            'min_length': 20
        }
    }

    def __init__(self, api_key: str, prompts_dir: str = "config/prompts"):
        """
        Initialize PostGenerator.

        Args:
            api_key: Anthropic API key
            prompts_dir: Directory containing prompt files

        Raises:
            ValueError: If API key is empty
        """
        if not api_key:
            raise ValueError("Anthropic API key is required")

        self.api_key = api_key
        self.prompts_dir = prompts_dir
        self._client = None

    @property
    def client(self):
        """Lazy initialization of Anthropic client."""
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def load_prompt_from_file(self, platform: str) -> Dict[str, str]:
        """
        Load prompt configuration from file.

        Args:
            platform: Platform name (e.g., 'threads')

        Returns:
            Dictionary with 'system' and 'user_template' keys

        Raises:
            FileNotFoundError: If prompt file not found
        """
        prompt_file = Path(self.prompts_dir) / f"{platform}.yaml"

        if not prompt_file.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_file}")

        with open(prompt_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        return {
            'system': config.get('system_prompt', ''),
            'user_template': config.get('user_template', '')
        }

    def format_prompt(
        self,
        template: str,
        transcript: str,
        video_metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Format prompt template with transcript and metadata.

        Args:
            template: Prompt template string
            transcript: Video transcript
            video_metadata: Optional video metadata

        Returns:
            Formatted prompt string
        """
        format_vars = {
            'transcript': transcript
        }

        # Add video metadata if provided
        if video_metadata:
            format_vars.update(video_metadata)

        return template.format(**format_vars)

    def generate_post(
        self,
        transcript: str,
        platform: str = 'threads',
        video_metadata: Optional[Dict[str, Any]] = None,
        custom_instructions: Optional[str] = None,
        model: str = "claude-3-5-sonnet-20241022"
    ) -> GeneratedPost:
        """
        Generate social media post from transcript.

        Args:
            transcript: Video transcript
            platform: Platform name (e.g., 'threads')
            video_metadata: Optional video metadata
            custom_instructions: Optional custom instructions
            model: Claude model to use

        Returns:
            GeneratedPost object

        Raises:
            ValueError: If transcript is empty or platform unsupported
            Exception: If API call fails
        """
        # Validate inputs
        if not transcript or not transcript.strip():
            raise ValueError("Transcript cannot be empty")

        if platform not in self.PLATFORM_LIMITS:
            raise ValueError(f"Unsupported platform: {platform}")

        # Load prompt configuration
        try:
            prompt_config = self.load_prompt_from_file(platform)
        except FileNotFoundError:
            raise ValueError(f"Unsupported platform: {platform}")

        # Format user prompt
        user_prompt = self.format_prompt(
            template=prompt_config['user_template'],
            transcript=transcript,
            video_metadata=video_metadata
        )

        # Add custom instructions if provided
        if custom_instructions:
            user_prompt += f"\n\nДополнительные инструкции: {custom_instructions}"

        # Call Claude API
        response = self.client.messages.create(
            model=model,
            max_tokens=1024,
            system=prompt_config['system'],
            messages=[
                {
                    "role": "user",
                    "content": user_prompt
                }
            ]
        )

        # Extract generated content
        generated_content = response.content[0].text

        # Create GeneratedPost object
        post = GeneratedPost(
            platform=platform,
            content=generated_content,
            hashtags=self.extract_hashtags(generated_content),
            emoji_count=self.count_emojis(generated_content),
            char_count=len(generated_content)
        )

        return post

    def generate_post_with_retry(
        self,
        transcript: str,
        platform: str = 'threads',
        video_metadata: Optional[Dict[str, Any]] = None,
        custom_instructions: Optional[str] = None,
        max_retries: int = 3,
        model: str = "claude-3-5-sonnet-20241022"
    ) -> GeneratedPost:
        """
        Generate post with retry logic.

        Args:
            transcript: Video transcript
            platform: Platform name
            video_metadata: Optional video metadata
            custom_instructions: Optional custom instructions
            max_retries: Maximum retry attempts
            model: Claude model to use

        Returns:
            GeneratedPost object

        Raises:
            Exception: If all retries fail
        """
        last_exception = None

        for attempt in range(max_retries):
            try:
                return self.generate_post(
                    transcript=transcript,
                    platform=platform,
                    video_metadata=video_metadata,
                    custom_instructions=custom_instructions,
                    model=model
                )
            except anthropic.RateLimitError:
                # Don't retry rate limit errors
                raise
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    # Wait before retry (exponential backoff)
                    time.sleep(2 ** attempt)
                    continue
                else:
                    raise

        # If we get here, all retries failed
        if last_exception:
            raise last_exception

    def validate_post_length(self, post: str, platform: str) -> bool:
        """
        Validate post length for platform.

        Args:
            post: Post content
            platform: Platform name

        Returns:
            True if valid length

        Raises:
            ValueError: If platform unknown
        """
        if platform not in self.PLATFORM_LIMITS:
            raise ValueError(f"Unknown platform: {platform}")

        limits = self.PLATFORM_LIMITS[platform]
        max_len = limits['max_length']

        return len(post) <= max_len

    def extract_hashtags(self, post: str) -> List[str]:
        """
        Extract hashtags from post.

        Args:
            post: Post content

        Returns:
            List of hashtags (including #)
        """
        return re.findall(r'#\w+', post)

    def count_emojis(self, post: str) -> int:
        """
        Count emojis in post.

        Args:
            post: Post content

        Returns:
            Number of emojis
        """
        # Unicode emoji ranges (comprehensive)
        emoji_pattern = re.compile(
            "["
            "\U0001F1E0-\U0001F1FF"  # flags (iOS)
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F700-\U0001F77F"  # alchemical symbols
            "\U0001F780-\U0001F7FF"  # Geometric Shapes Extended
            "\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
            "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
            "\U0001FA00-\U0001FA6F"  # Chess Symbols
            "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
            "\U00002702-\U000027B0"  # Dingbats
            "\U000024C2-\U0001F251"
            "]+",
            flags=re.UNICODE
        )
        return len(emoji_pattern.findall(post))

    def truncate_post(self, post: str, platform: str) -> str:
        """
        Truncate post if too long for platform.

        Args:
            post: Post content
            platform: Platform name

        Returns:
            Truncated post with "..." suffix
        """
        limits = self.PLATFORM_LIMITS.get(platform, {})
        max_len = limits.get('max_length', 500)

        if len(post) <= max_len:
            return post

        # Truncate and add ellipsis
        return post[:max_len - 3] + "..."

    def get_platform_limits(self) -> Dict[str, Dict[str, int]]:
        """
        Get platform character limits.

        Returns:
            Dictionary of platform limits
        """
        return self.PLATFORM_LIMITS
