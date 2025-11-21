"""
AI Transcriber using youtube-transcript-api (priority) with Whisper fallback.

Extracts transcripts from YouTube videos.
"""
import re
from dataclasses import dataclass
from typing import Optional, List
from urllib.parse import urlparse, parse_qs

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable
)


@dataclass
class TranscriptionResult:
    """Dataclass representing transcription result."""
    text: str
    language: Optional[str] = None
    source: str = "youtube_captions"
    duration: Optional[float] = None
    word_count: Optional[int] = None
    has_timestamps: bool = False


class Transcriber:
    """Transcriber for extracting transcripts from YouTube videos."""

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        use_youtube_captions: bool = True,
        enable_whisper_fallback: bool = False
    ):
        """
        Initialize Transcriber.

        Args:
            openai_api_key: OpenAI API key for Whisper (optional)
            use_youtube_captions: Use YouTube captions as priority (default: True)
            enable_whisper_fallback: Enable Whisper API fallback (default: False)

        Raises:
            ValueError: If Whisper fallback enabled without API key
        """
        self.openai_api_key = openai_api_key
        self.use_youtube_captions = use_youtube_captions
        self.enable_whisper_fallback = enable_whisper_fallback

        if enable_whisper_fallback and not openai_api_key:
            raise ValueError("OpenAI API key required for fallback")

    def extract_video_id(self, url: str) -> str:
        """
        Extract video ID from YouTube URL.

        Args:
            url: YouTube URL

        Returns:
            Video ID

        Raises:
            ValueError: If invalid YouTube URL
        """
        # Parse URL
        parsed = urlparse(url)

        # Check for different YouTube URL formats
        if 'youtube.com' in parsed.netloc:
            # Standard format: https://www.youtube.com/watch?v=VIDEO_ID
            query_params = parse_qs(parsed.query)
            if 'v' in query_params:
                return query_params['v'][0]
        elif 'youtu.be' in parsed.netloc:
            # Short format: https://youtu.be/VIDEO_ID
            return parsed.path.lstrip('/')

        raise ValueError("Invalid YouTube URL")

    def get_youtube_transcript(
        self,
        video_id: str,
        language: Optional[str] = None,
        languages: Optional[List[str]] = None
    ) -> TranscriptionResult:
        """
        Get transcript from YouTube captions.

        Args:
            video_id: YouTube video ID
            language: Preferred language code (e.g., 'ru', 'en')
            languages: List of language codes to try (fallback)

        Returns:
            TranscriptionResult object

        Raises:
            TranscriptsDisabled: If transcripts are disabled for video
            NoTranscriptFound: If no transcript found in specified language
        """
        # Determine which languages to try
        if languages:
            lang_list = languages
        elif language:
            lang_list = [language]
        else:
            lang_list = ["ru", "en"]  # Default fallback

        # Try to get transcript
        try:
            transcript_segments = YouTubeTranscriptApi.get_transcript(
                video_id,
                languages=lang_list
            )
        except NoTranscriptFound:
            # Try again with first language only if list was provided
            if len(lang_list) > 1:
                transcript_segments = YouTubeTranscriptApi.get_transcript(
                    video_id,
                    languages=[lang_list[1]]  # Try second language
                )
            else:
                raise

        # Format transcript to plain text
        text = self.format_transcript_to_text(transcript_segments)

        # Create result
        result = TranscriptionResult(
            text=text,
            language=language or lang_list[0],
            source="youtube_captions",
            has_timestamps=True,
            word_count=len(text.split())
        )

        return result

    def format_transcript_to_text(self, transcript_segments: List[dict]) -> str:
        """
        Format transcript segments to plain text.

        Args:
            transcript_segments: List of transcript segment dictionaries

        Returns:
            Formatted text string
        """
        if not transcript_segments:
            return ""

        # Extract text from each segment and join
        texts = [segment['text'] for segment in transcript_segments]
        return " ".join(texts)

    def format_transcript_with_timestamps(self, transcript_segments: List[dict]) -> str:
        """
        Format transcript with timestamps.

        Args:
            transcript_segments: List of transcript segment dictionaries

        Returns:
            Formatted text with timestamps
        """
        formatted = []
        for segment in transcript_segments:
            timestamp = f"[{segment['start']:.1f}s]"
            text = segment['text']
            formatted.append(f"{timestamp} {text}")

        return "\n".join(formatted)

    def get_available_languages(self, video_id: str) -> List[str]:
        """
        Get list of available transcript languages for a video.

        Args:
            video_id: YouTube video ID

        Returns:
            List of available language codes
        """
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        languages = [transcript.language_code for transcript in transcript_list]
        return languages

    def transcribe(
        self,
        video_id: str,
        language: Optional[str] = "ru"
    ) -> TranscriptionResult:
        """
        Transcribe video (main method).

        Priority: YouTube captions → Whisper API fallback

        Args:
            video_id: YouTube video ID
            language: Preferred language code

        Returns:
            TranscriptionResult object

        Raises:
            Exception: If both YouTube captions and Whisper fail
        """
        if self.use_youtube_captions:
            try:
                return self.get_youtube_transcript(video_id, language=language)
            except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable) as e:
                if self.enable_whisper_fallback:
                    # TODO: Implement Whisper fallback
                    return self.transcribe_with_whisper(video_id, language)
                else:
                    raise
        else:
            # Use Whisper directly if YouTube captions disabled
            return self.transcribe_with_whisper(video_id, language)

    def transcribe_with_whisper(self, video_id: str, language: Optional[str]) -> TranscriptionResult:
        """
        Transcribe using OpenAI Whisper API (fallback).

        Args:
            video_id: YouTube video ID
            language: Language code

        Returns:
            TranscriptionResult object

        Note: This is a placeholder for Whisper implementation
        """
        # TODO: Implement actual Whisper API integration
        # For now, raise NotImplementedError
        raise NotImplementedError("Whisper fallback not implemented in MVP")

    def get_youtube_transcript_with_retry(
        self,
        video_id: str,
        language: str = "ru",
        max_retries: int = 3
    ) -> TranscriptionResult:
        """
        Get YouTube transcript with retry logic.

        Args:
            video_id: YouTube video ID
            language: Language code
            max_retries: Maximum number of retry attempts

        Returns:
            TranscriptionResult object

        Raises:
            Exception: If all retries fail
        """
        last_exception = None

        for attempt in range(max_retries):
            try:
                return self.get_youtube_transcript(video_id, language=language)
            except ConnectionError as e:
                last_exception = e
                if attempt < max_retries - 1:
                    # Wait before retry (exponential backoff could be added here)
                    continue
                else:
                    raise

        # If we get here, all retries failed
        if last_exception:
            raise last_exception
        else:
            raise Exception("Transcription failed after retries")

    def clean_transcript_text(self, text: str) -> str:
        """
        Clean transcript text from artifacts.

        Args:
            text: Raw transcript text

        Returns:
            Cleaned text
        """
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)

        # Trim leading/trailing whitespace
        text = text.strip()

        return text

    def calculate_transcript_stats(self, text: str) -> dict:
        """
        Calculate statistics for transcript.

        Args:
            text: Transcript text

        Returns:
            Dictionary with statistics
        """
        # Count sentences by looking for sentence-ending punctuation
        sentence_count = len(re.findall(r'[.!?]+', text))

        return {
            'char_count': len(text),
            'word_count': len(text.split()),
            'line_count': text.count('\n') + 1 if text else 0,
            'sentence_count': sentence_count,
            'alpha_ratio': sum(c.isalpha() for c in text) / len(text) if text else 0
        }

    def normalize_language_code(self, language_code: str) -> str:
        """
        Normalize language code to standard format.

        Args:
            language_code: Language code (e.g., 'ru-RU', 'en-US')

        Returns:
            Normalized language code (e.g., 'ru', 'en')
        """
        # Extract base language code (before hyphen)
        return language_code.split('-')[0].lower()
