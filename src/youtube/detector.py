"""
YouTube RSS Feed Detector.

Monitors YouTube channels for new videos using RSS feeds.
"""
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List

import requests


@dataclass
class Video:
    """Dataclass representing a YouTube video."""
    video_id: str
    title: str
    url: str
    description: str
    published_date: datetime
    thumbnail_url: str


class YouTubeDetector:
    """YouTube RSS feed detector for monitoring new videos."""

    def __init__(self, channel_id: str):
        """
        Initialize YouTube detector.

        Args:
            channel_id: YouTube channel ID

        Raises:
            ValueError: If channel_id is empty
        """
        if not channel_id or channel_id.strip() == "":
            raise ValueError("Channel ID cannot be empty")

        self.channel_id = channel_id
        self.rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

    def fetch_rss_feed(self, timeout: int = 10) -> str:
        """
        Fetch RSS feed from YouTube.

        Args:
            timeout: Request timeout in seconds

        Returns:
            RSS feed XML as string

        Raises:
            Exception: If request fails
        """
        response = requests.get(self.rss_url, timeout=timeout)
        response.raise_for_status()
        return response.text

    def parse_rss_feed(self, feed_xml: str) -> List[Video]:
        """
        Parse RSS feed XML and extract video information.

        Args:
            feed_xml: RSS feed XML string

        Returns:
            List of Video objects

        Raises:
            Exception: If XML parsing fails
        """
        try:
            root = ET.fromstring(feed_xml)
        except ET.ParseError as e:
            raise Exception(f"Failed to parse XML: {e}")

        videos = []

        # Define namespaces used in YouTube RSS feed
        namespaces = {
            'atom': 'http://www.w3.org/2005/Atom',
            'yt': 'http://www.youtube.com/xml/schemas/2015',
            'media': 'http://search.yahoo.com/mrss/'
        }

        # Find all entry elements (videos)
        entries = root.findall('atom:entry', namespaces)

        for entry in entries:
            try:
                # Extract video data
                video_id = entry.find('yt:videoId', namespaces)
                title = entry.find('atom:title', namespaces)
                link = entry.find('atom:link', namespaces)
                published = entry.find('atom:published', namespaces)

                # Extract media group data
                media_group = entry.find('media:group', namespaces)
                description_elem = media_group.find('media:description', namespaces) if media_group is not None else None
                thumbnail_elem = media_group.find('media:thumbnail', namespaces) if media_group is not None else None

                # Create Video object
                video = Video(
                    video_id=video_id.text if video_id is not None else "",
                    title=title.text if title is not None else "",
                    url=link.get('href') if link is not None else "",
                    description=description_elem.text if description_elem is not None else "",
                    published_date=datetime.fromisoformat(published.text.replace('Z', '+00:00')) if published is not None else datetime.now(),
                    thumbnail_url=thumbnail_elem.get('url') if thumbnail_elem is not None else ""
                )

                videos.append(video)

            except Exception as e:
                # Skip malformed entries
                continue

        return videos

    def filter_new_videos(self, videos: List[Video], hours: float = 24) -> List[Video]:
        """
        Filter videos published within specified timeframe.

        Args:
            videos: List of Video objects
            hours: Timeframe in hours (default: 24)

        Returns:
            List of Video objects published within timeframe
        """
        now = datetime.now(videos[0].published_date.tzinfo if videos and videos[0].published_date.tzinfo else None)
        cutoff_time = now - timedelta(hours=hours)

        new_videos = [
            video for video in videos
            if video.published_date >= cutoff_time
        ]

        return new_videos

    def check_for_new_videos(self, hours: float = 24) -> List[Video]:
        """
        Check for new videos published within specified timeframe.

        This is the main method that combines fetching, parsing, and filtering.

        Args:
            hours: Timeframe in hours to check for new videos (default: 24)

        Returns:
            List of new Video objects

        Raises:
            Exception: If fetching or parsing fails
        """
        # Fetch RSS feed
        feed_xml = self.fetch_rss_feed()

        # Parse feed
        videos = self.parse_rss_feed(feed_xml)

        # Filter for new videos
        if videos:
            new_videos = self.filter_new_videos(videos, hours=hours)
            return new_videos
        else:
            return []
