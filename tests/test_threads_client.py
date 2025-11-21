"""
Unit tests for Threads API Client.

Tests cover:
- Post publishing to Threads
- Authentication
- Error handling
- Rate limiting
- Response validation
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.social.threads_client import ThreadsClient, PublishResult, ThreadsAPIError


class TestThreadsClient:
    """Test suite for ThreadsClient class."""

    @pytest.fixture
    def client(self):
        """Create ThreadsClient instance for testing."""
        return ThreadsClient(
            access_token="test_access_token_123",
            user_id="test_user_id_456"
        )

    @pytest.fixture
    def sample_post_content(self):
        """Sample post content for testing."""
        return """
        🩺 Витамин D - ключ к здоровью!

        Особенно важен зимой для иммунитета.

        ⚠️ Это общая информация, не медицинская рекомендация.

        #здоровье #витаминD
        """

    def test_init_with_credentials(self, client):
        """Test initialization with access token and user ID."""
        assert client.access_token == "test_access_token_123"
        assert client.user_id == "test_user_id_456"
        assert client.base_url == "https://graph.threads.net/v1.0"

    def test_init_without_access_token(self):
        """Test initialization without access token raises ValueError."""
        with pytest.raises(ValueError, match="Access token is required"):
            ThreadsClient(access_token="", user_id="test_user")

    def test_init_without_user_id(self):
        """Test initialization without user ID raises ValueError."""
        with pytest.raises(ValueError, match="User ID is required"):
            ThreadsClient(access_token="test_token", user_id="")

    @patch('requests.post')
    def test_publish_post_success(self, mock_post, client, sample_post_content):
        """Test successful post publishing."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'id': 'thread_123456',
            'permalink': 'https://www.threads.net/@username/post/thread_123456'
        }
        mock_post.return_value = mock_response

        result = client.publish_post(sample_post_content)

        assert isinstance(result, PublishResult)
        assert result.success is True
        assert result.post_id == 'thread_123456'
        assert 'threads.net' in result.post_url
        mock_post.assert_called_once()

    @patch('requests.post')
    def test_publish_post_with_retry_on_failure(self, mock_post, client, sample_post_content):
        """Test publishing with retry on temporary failure."""
        # First call fails, second succeeds
        mock_response_fail = Mock()
        mock_response_fail.status_code = 500
        mock_response_fail.raise_for_status.side_effect = Exception("Server error")

        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {
            'id': 'thread_retry_123',
            'permalink': 'https://www.threads.net/@username/post/thread_retry_123'
        }

        mock_post.side_effect = [mock_response_fail, mock_response_success]

        result = client.publish_post_with_retry(sample_post_content, max_retries=2)

        assert result.success is True
        assert result.post_id == 'thread_retry_123'
        assert mock_post.call_count == 2

    @patch('requests.post')
    def test_publish_post_authentication_error(self, mock_post, client, sample_post_content):
        """Test publishing with authentication error."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {
            'error': {'message': 'Invalid OAuth access token'}
        }
        mock_post.return_value = mock_response

        with pytest.raises(ThreadsAPIError, match="Authentication failed"):
            client.publish_post(sample_post_content)

    @patch('requests.post')
    def test_publish_post_rate_limit_error(self, mock_post, client, sample_post_content):
        """Test publishing with rate limit error."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.json.return_value = {
            'error': {'message': 'Rate limit exceeded'}
        }
        mock_post.return_value = mock_response

        with pytest.raises(ThreadsAPIError, match="Rate limit exceeded"):
            client.publish_post(sample_post_content)

    @patch('requests.post')
    def test_publish_post_content_too_long(self, mock_post, client):
        """Test publishing post that exceeds character limit."""
        long_content = "A" * 600  # Exceeds 500 char limit

        with pytest.raises(ValueError, match="Post content exceeds"):
            client.publish_post(long_content)

        mock_post.assert_not_called()

    @patch('requests.post')
    def test_publish_post_empty_content(self, mock_post, client):
        """Test publishing empty post."""
        with pytest.raises(ValueError, match="Post content cannot be empty"):
            client.publish_post("")

        mock_post.assert_not_called()

    def test_validate_post_content_valid(self, client, sample_post_content):
        """Test validating valid post content."""
        is_valid, errors = client.validate_post_content(sample_post_content)

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_post_content_too_long(self, client):
        """Test validating post content that's too long."""
        long_content = "A" * 600

        is_valid, errors = client.validate_post_content(long_content)

        assert is_valid is False
        assert any('length' in error.lower() for error in errors)

    def test_validate_post_content_empty(self, client):
        """Test validating empty post content."""
        is_valid, errors = client.validate_post_content("")

        assert is_valid is False
        assert any('empty' in error.lower() for error in errors)

    @patch('requests.get')
    def test_get_post_details(self, mock_get, client):
        """Test fetching post details."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'id': 'thread_123',
            'text': 'Post content',
            'timestamp': '2025-11-20T10:00:00+0000',
            'permalink': 'https://www.threads.net/@username/post/thread_123'
        }
        mock_get.return_value = mock_response

        post_details = client.get_post_details('thread_123')

        assert post_details['id'] == 'thread_123'
        assert 'text' in post_details
        mock_get.assert_called_once()

    @patch('requests.delete')
    def test_delete_post_success(self, mock_delete, client):
        """Test successful post deletion."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'success': True}
        mock_delete.return_value = mock_response

        result = client.delete_post('thread_123')

        assert result is True
        mock_delete.assert_called_once()

    @patch('requests.delete')
    def test_delete_post_not_found(self, mock_delete, client):
        """Test deleting non-existent post."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {
            'error': {'message': 'Post not found'}
        }
        mock_delete.return_value = mock_response

        with pytest.raises(ThreadsAPIError, match="Post not found"):
            client.delete_post('nonexistent_post')

    def test_format_api_url(self, client):
        """Test formatting API endpoint URLs."""
        endpoint = "me/threads"

        url = client.format_api_url(endpoint)

        assert url.startswith("https://graph.threads.net/v1.0")
        assert client.user_id in url
        assert "threads" in url

    def test_build_request_headers(self, client):
        """Test building request headers."""
        headers = client.build_request_headers()

        assert 'Authorization' in headers
        assert 'Bearer test_access_token_123' in headers['Authorization']
        assert 'Content-Type' in headers

    @patch('requests.post')
    def test_publish_with_media(self, mock_post, client):
        """Test publishing post with media (not supported in MVP)."""
        # For MVP, media posts are not supported
        with pytest.raises(NotImplementedError, match="Media posts not supported"):
            client.publish_post_with_media("Content", media_url="https://example.com/image.jpg")

    def test_extract_post_id_from_response(self, client):
        """Test extracting post ID from API response."""
        response_data = {
            'id': 'thread_xyz_123',
            'other_field': 'value'
        }

        post_id = client.extract_post_id(response_data)

        assert post_id == 'thread_xyz_123'

    def test_extract_post_url_from_response(self, client):
        """Test extracting post URL from API response."""
        response_data = {
            'permalink': 'https://www.threads.net/@username/post/abc123'
        }

        post_url = client.extract_post_url(response_data)

        assert 'threads.net' in post_url
        assert 'abc123' in post_url

    def test_publish_result_dataclass(self):
        """Test PublishResult dataclass attributes."""
        result = PublishResult(
            success=True,
            post_id='thread_123',
            post_url='https://www.threads.net/@user/post/thread_123',
            platform='threads',
            timestamp='2025-11-20T10:00:00Z'
        )

        assert result.success is True
        assert result.post_id == 'thread_123'
        assert result.platform == 'threads'
        assert 'threads.net' in result.post_url

    @patch('requests.get')
    def test_check_api_health(self, mock_get, client):
        """Test checking API health/connectivity."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        is_healthy = client.check_api_health()

        assert is_healthy is True

    @patch('requests.get')
    def test_check_api_health_failure(self, mock_get, client):
        """Test API health check when API is down."""
        mock_get.side_effect = ConnectionError("Cannot connect")

        is_healthy = client.check_api_health()

        assert is_healthy is False

    def test_count_characters(self, client, sample_post_content):
        """Test counting characters in post content."""
        char_count = client.count_characters(sample_post_content)

        assert char_count > 0
        assert char_count == len(sample_post_content)

    @pytest.mark.parametrize("content,expected_valid", [
        ("Short post", True),
        ("A" * 500, True),  # Exactly at limit
        ("A" * 501, False),  # Over limit
        ("", False),  # Empty
    ])
    def test_validate_content_length_parametrized(self, client, content, expected_valid):
        """Test content length validation with various inputs."""
        is_valid, _ = client.validate_post_content(content)
        assert is_valid == expected_valid

    @patch('requests.post')
    def test_publish_post_network_error(self, mock_post, client, sample_post_content):
        """Test publishing post with network error."""
        mock_post.side_effect = ConnectionError("Network error")

        with pytest.raises(ConnectionError):
            client.publish_post(sample_post_content)

    @patch('requests.post')
    def test_publish_post_timeout(self, mock_post, client, sample_post_content):
        """Test publishing post with timeout."""
        import requests
        mock_post.side_effect = requests.Timeout("Request timeout")

        with pytest.raises(requests.Timeout):
            client.publish_post(sample_post_content)

    def test_parse_error_response(self, client):
        """Test parsing error response from API."""
        error_response = {
            'error': {
                'message': 'Invalid access token',
                'type': 'OAuthException',
                'code': 190
            }
        }

        error_info = client.parse_error_response(error_response)

        assert error_info['message'] == 'Invalid access token'
        assert error_info['type'] == 'OAuthException'
        assert error_info['code'] == 190

    @patch('requests.post')
    def test_publish_with_exponential_backoff(self, mock_post, client, sample_post_content):
        """Test publishing with exponential backoff on rate limit."""
        # Simulate rate limit then success
        mock_response_limit = Mock()
        mock_response_limit.status_code = 429

        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {'id': 'thread_success'}

        mock_post.side_effect = [mock_response_limit, mock_response_success]

        result = client.publish_with_backoff(sample_post_content, initial_delay=0.1)

        assert result.success is True
        assert mock_post.call_count == 2
