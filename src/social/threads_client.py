"""
Threads API Client for publishing posts.

Handles authentication, posting, error handling, and rate limiting.
"""
import time
import requests
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple


class ThreadsAPIError(Exception):
    """Custom exception for Threads API errors."""
    pass


@dataclass
class PublishResult:
    """Result of publishing a post."""
    success: bool
    post_id: Optional[str] = None
    post_url: Optional[str] = None
    error_message: Optional[str] = None
    platform: str = "threads"


class ThreadsClient:
    """Client for Threads API operations."""

    # API base URL
    BASE_URL = "https://graph.threads.net/v1.0"

    # Content limits
    MAX_POST_LENGTH = 500

    def __init__(self, access_token: str, user_id: str):
        """
        Initialize Threads client.

        Args:
            access_token: Threads API access token
            user_id: User ID for the Threads account

        Raises:
            ValueError: If credentials are missing
        """
        if not access_token:
            raise ValueError("Access token is required")
        if not user_id:
            raise ValueError("User ID is required")

        self.access_token = access_token
        self.user_id = user_id
        self.base_url = self.BASE_URL

    def publish_post(
        self,
        content: str,
        media_url: Optional[str] = None
    ) -> PublishResult:
        """
        Publish a post to Threads.

        Args:
            content: Post content text
            media_url: Optional media URL

        Returns:
            PublishResult object

        Raises:
            ThreadsAPIError: If API call fails
            ValueError: If content is invalid
        """
        # Validate content
        is_valid, errors = self.validate_post_content(content)
        if not is_valid:
            raise ValueError("; ".join(errors))

        # Build API URL
        url = self.format_api_url(f"me/threads")

        # Build request payload
        payload = {
            'media_type': 'TEXT',
            'text': content,
            'access_token': self.access_token
        }

        if media_url:
            payload['image_url'] = media_url

        # Make API request
        try:
            headers = self.build_request_headers()
            response = requests.post(url, json=payload, headers=headers, timeout=30)

            # Handle different status codes
            if response.status_code == 200:
                data = response.json()
                post_id = self.extract_post_id(data)
                post_url = self.extract_post_url(data)

                return PublishResult(
                    success=True,
                    post_id=post_id,
                    post_url=post_url,
                    platform="threads"
                )
            elif response.status_code == 401:
                error_msg = self.parse_error_response(response)
                raise ThreadsAPIError(f"Authentication failed: {error_msg}")
            elif response.status_code == 429:
                error_msg = self.parse_error_response(response)
                raise ThreadsAPIError(f"Rate limit exceeded: {error_msg}")
            else:
                error_msg = self.parse_error_response(response)
                return PublishResult(
                    success=False,
                    error_message=f"API error: {error_msg}",
                    platform="threads"
                )

        except requests.exceptions.Timeout:
            raise ThreadsAPIError("Request timeout")
        except requests.exceptions.RequestException as e:
            raise ThreadsAPIError(f"Network error: {str(e)}")

    def publish_post_with_retry(
        self,
        content: str,
        media_url: Optional[str] = None,
        max_retries: int = 3
    ) -> PublishResult:
        """
        Publish post with retry logic and exponential backoff.

        Args:
            content: Post content
            media_url: Optional media URL
            max_retries: Maximum retry attempts

        Returns:
            PublishResult object
        """
        last_error = None

        for attempt in range(max_retries):
            try:
                return self.publish_post(content, media_url)
            except ThreadsAPIError as e:
                last_error = e
                # Don't retry auth or rate limit errors
                if "Authentication" in str(e) or "Rate limit" in str(e):
                    raise

                if attempt < max_retries - 1:
                    # Exponential backoff: 2^attempt seconds
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                    continue
                else:
                    raise

        # If we get here, all retries failed
        if last_error:
            raise last_error

        return PublishResult(success=False, error_message="All retries failed", platform="threads")

    def publish_with_retry(
        self,
        content: str,
        media_url: Optional[str] = None,
        max_retries: int = 3
    ) -> PublishResult:
        """Alias for publish_post_with_retry."""
        return self.publish_post_with_retry(content, media_url, max_retries)

    def publish_with_backoff(
        self,
        content: str,
        max_retries: int = 3
    ) -> PublishResult:
        """Alias for publish_post_with_retry."""
        return self.publish_post_with_retry(content, max_retries=max_retries)

    def publish_post_with_media(self, content: str, media_url: str) -> PublishResult:
        """
        Publish post with media (not supported in MVP).

        Args:
            content: Post content
            media_url: Media URL

        Raises:
            NotImplementedError: Media posts not supported in MVP
        """
        raise NotImplementedError("Media posts not supported in MVP")

    def validate_post_content(self, content: str) -> Tuple[bool, List[str]]:
        """
        Validate post content.

        Args:
            content: Post content

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        if not content or not content.strip():
            errors.append("Content cannot be empty")

        if len(content) > self.MAX_POST_LENGTH:
            errors.append(f"Content exceeds maximum length of {self.MAX_POST_LENGTH} characters")

        is_valid = len(errors) == 0
        return (is_valid, errors)

    def get_post_details(self, post_id: str) -> Dict[str, Any]:
        """
        Get details of a published post.

        Args:
            post_id: Post ID

        Returns:
            Post details dictionary

        Raises:
            ThreadsAPIError: If API call fails
        """
        url = self.format_api_url(post_id)
        params = {'access_token': self.access_token}
        headers = self.build_request_headers()

        try:
            response = requests.get(url, params=params, headers=headers, timeout=30)

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                raise ThreadsAPIError("Post not found")
            else:
                error_msg = self.parse_error_response(response)
                raise ThreadsAPIError(f"Failed to get post details: {error_msg}")

        except requests.exceptions.RequestException as e:
            raise ThreadsAPIError(f"Network error: {str(e)}")

    def delete_post(self, post_id: str) -> bool:
        """
        Delete a post.

        Args:
            post_id: Post ID

        Returns:
            True if deleted successfully

        Raises:
            ThreadsAPIError: If API call fails
        """
        url = self.format_api_url(post_id)
        params = {'access_token': self.access_token}
        headers = self.build_request_headers()

        try:
            response = requests.delete(url, params=params, headers=headers, timeout=30)

            if response.status_code == 200:
                return True
            elif response.status_code == 404:
                raise ThreadsAPIError("Post not found")
            else:
                error_msg = self.parse_error_response(response)
                raise ThreadsAPIError(f"Failed to delete post: {error_msg}")

        except requests.exceptions.RequestException as e:
            raise ThreadsAPIError(f"Network error: {str(e)}")

    def format_api_url(self, endpoint: str) -> str:
        """
        Format API URL, replacing 'me' with user_id.

        Args:
            endpoint: API endpoint

        Returns:
            Full API URL
        """
        # Remove leading slash if present
        endpoint = endpoint.lstrip('/')

        # Replace 'me' with actual user_id
        endpoint = endpoint.replace('me', self.user_id)

        return f"{self.base_url}/{endpoint}"

    def build_request_headers(self) -> Dict[str, str]:
        """
        Build request headers with authorization.

        Returns:
            Headers dictionary
        """
        return {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Bearer {self.access_token}'
        }

    def extract_post_id(self, response_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract post ID from API response.

        Args:
            response_data: Response data dictionary

        Returns:
            Post ID or None
        """
        return response_data.get('id')

    def extract_post_url(self, response_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract post URL from API response.

        Args:
            response_data: Response data dictionary

        Returns:
            Post URL or None
        """
        return response_data.get('permalink')

    # Aliases for compatibility
    def extract_post_id_from_response(self, response_data: Dict[str, Any]) -> Optional[str]:
        """Alias for extract_post_id."""
        return self.extract_post_id(response_data)

    def extract_post_url_from_response(self, response_data: Dict[str, Any]) -> Optional[str]:
        """Alias for extract_post_url."""
        return self.extract_post_url(response_data)

    def parse_error_response(self, response) -> str:
        """
        Parse error message from API response or dict.

        Args:
            response: Response object or dict

        Returns:
            Error message string
        """
        # Handle dict input (for tests)
        if isinstance(response, dict):
            if 'error' in response:
                error_info = response['error']
                if isinstance(error_info, dict):
                    return error_info.get('message', 'Unknown error')
                return str(error_info)
            return response.get('message', 'Unknown error')

        # Handle Response object
        try:
            error_data = response.json()
            if 'error' in error_data:
                error_info = error_data['error']
                if isinstance(error_info, dict):
                    return error_info.get('message', 'Unknown error')
                return str(error_info)
            return error_data.get('message', 'Unknown error')
        except Exception:
            return f"HTTP {response.status_code}: {response.text}"

    def check_api_health(self) -> bool:
        """
        Check if Threads API is reachable.

        Returns:
            True if API is healthy

        Raises:
            ThreadsAPIError: If health check fails
        """
        url = f"{self.base_url}/healthcheck"

        try:
            response = requests.get(url, timeout=10)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            raise ThreadsAPIError("API health check failed")

    def count_characters(self, text: str) -> int:
        """
        Count characters in text.

        Args:
            text: Text to count

        Returns:
            Character count
        """
        return len(text)
